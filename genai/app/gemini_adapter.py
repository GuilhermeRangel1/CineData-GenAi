"""Adaptador Gemini para a porta interna de tool calling."""

import json
import logging
from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

from app.agent_models import ModelTurn, ToolCall, ToolDefinition
from app.complexity_router import QuestionComplexity
from app.errors import ProviderConfigurationError, ProviderTransientError


logger = logging.getLogger(__name__)


class GeminiToolCallingModel:
    """Converte o contrato interno para a API de function calling do Gemini."""

    def __init__(
        self,
        api_key: str | None,
        model: str = "gemini-3.5-flash-lite",
        complex_model: str | None = "gemini-3.5-flash",
        fallback_model: str | None = "gemini-3.5-flash",
        client: Any = None,
    ):
        if not api_key and client is None:
            raise ProviderConfigurationError("A chave da Gemini API não foi configurada.")
        self.model = model
        self.complex_model = complex_model if complex_model and complex_model != model else None
        self.fallback_model = fallback_model if fallback_model and fallback_model != model else None
        self.client = client or genai.Client(api_key=api_key)

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[ToolDefinition],
    ) -> ModelTurn:
        """Executa uma inferência leve e normaliza texto ou pedido de ferramenta."""

        return self.complete_for_complexity(messages, tools, QuestionComplexity.SIMPLE)

    def complete_for_complexity(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[ToolDefinition],
        complexity: QuestionComplexity,
    ) -> ModelTurn:
        """Escolhe o modelo principal localmente; fallback continua só para falhas."""

        config = types.GenerateContentConfig(
            system_instruction=self._system_instruction(messages),
            temperature=0,
            **({"tools": [self._tool(tool) for tool in tools]} if tools else {}),
        )
        primary_model = (
            self.complex_model
            if complexity in {QuestionComplexity.HYBRID, QuestionComplexity.COMPLEX}
            and self.complex_model
            else self.model
        )
        # A configuração de fallback atende a rota leve. Quando a rota complexa
        # já usa esse mesmo modelo, o modelo leve passa a ser a alternativa para
        # manter uma tentativa real, sem repetir a mesma chamada.
        fallback_model = self.fallback_model
        if fallback_model == primary_model and primary_model != self.model:
            fallback_model = self.model
        models = (primary_model, *((fallback_model,) if fallback_model and fallback_model != primary_model else ()))
        for index, selected_model in enumerate(models):
            try:
                response = self.client.models.generate_content(
                    model=selected_model,
                    contents=self._contents(messages),
                    config=config,
                )
                result = self._normalize_response(response)
                logger.info(
                    "Gemini respondeu usando a rota %s e o modelo %s",
                    complexity,
                    selected_model,
                )
                return result
            except Exception as exc:
                can_fallback = index == 0 and self.fallback_model and self._is_transient_failure(exc)
                if not can_fallback:
                    raise
                logger.warning(
                    "Modelo Gemini %s indisponível (%s); tentando %s uma vez.",
                    selected_model,
                    exc.__class__.__name__,
                    self.fallback_model,
                )

        raise ProviderConfigurationError("Nenhum modelo Gemini está configurado.")

    @staticmethod
    def _normalize_response(response: Any) -> ModelTurn:
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if part.function_call:
                    return ModelTurn(
                        tool_call=ToolCall(
                            name=part.function_call.name,
                            arguments=dict(part.function_call.args or {}),
                            thought_signature=part.thought_signature,
                        )
                    )

        if response.text:
            return ModelTurn(answer=response.text)
        raise ProviderTransientError("O provedor não retornou conteúdo utilizável.")

    @staticmethod
    def _is_transient_failure(exc: Exception) -> bool:
        if isinstance(exc, ProviderTransientError | TimeoutError | ConnectionError | OSError):
            return True
        status = getattr(exc, "status_code", getattr(exc, "code", None))
        try:
            return int(status) in {408, 429, 500, 502, 503, 504}
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _tool(tool: ToolDefinition) -> types.Tool:
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters_json_schema=tool.parameters,
                )
            ]
        )

    @staticmethod
    def _system_instruction(messages: Sequence[dict[str, Any]]) -> str | None:
        instructions = [message["content"] for message in messages if message["role"] == "system"]
        return "\n".join(instructions) or None

    @staticmethod
    def _contents(messages: Sequence[dict[str, Any]]) -> list[types.Content]:
        contents: list[types.Content] = []
        for message in messages:
            role = message["role"]
            if role == "system":
                continue
            if role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message["content"])],
                    )
                )
            elif role == "assistant":
                call = message["tool_call"]
                contents.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name=call["name"],
                                    args=call["arguments"],
                                ),
                                thought_signature=call.get("thought_signature"),
                            )
                        ],
                    )
                )
            elif role == "tool":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=message["name"],
                                response=json.loads(message["content"]),
                            )
                        ],
                    )
                )
        return contents
