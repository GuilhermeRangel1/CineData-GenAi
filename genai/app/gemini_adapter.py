"""Adaptador Gemini para a porta interna de tool calling."""

import json
from collections.abc import Sequence
from typing import Any

from google import genai
from google.genai import types

from app.agent_models import ModelTurn, ToolCall, ToolDefinition
from app.errors import ProviderConfigurationError


class GeminiToolCallingModel:
    """Converte o contrato interno para a API de function calling do Gemini."""

    def __init__(
        self,
        api_key: str | None,
        model: str = "gemini-3.5-flash-lite",
        client: Any = None,
    ):
        if not api_key and client is None:
            raise ProviderConfigurationError("A chave da Gemini API não foi configurada.")
        self.model = model
        self.client = client or genai.Client(api_key=api_key)

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[ToolDefinition],
    ) -> ModelTurn:
        """Executa uma inferência e normaliza texto ou pedido de ferramenta."""

        response = self.client.models.generate_content(
            model=self.model,
            contents=self._contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=self._system_instruction(messages),
                tools=[self._tool(tool) for tool in tools],
                temperature=0,
            ),
        )
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

        return ModelTurn(answer=response.text or None)

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
