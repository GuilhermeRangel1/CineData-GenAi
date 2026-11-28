"""Tradução do contrato interno para Groq e OpenRouter Chat Completions."""

import asyncio
import json
from collections.abc import Sequence
from contextlib import nullcontext
from typing import Any

import httpx

from app.agent_models import ModelTurn, ToolCall
from app.errors import ProviderTransientError

ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}


class OpenAICompatibleModel:
    """Usa um endpoint fixo e um modelo explicitamente configurado, sem retries."""

    def __init__(self, provider: str, api_key: str, model: str, *, client=None):
        self.provider = provider
        self.model = model
        self._api_key = api_key
        self.client = client
        self.endpoint = ENDPOINTS[provider]

    def complete(self, messages, tools) -> ModelTurn:
        return self.complete_for_complexity(messages, tools, None)

    def complete_for_complexity(
        self, messages, tools, complexity, *, timeout_seconds: float = 12,
    ) -> ModelTurn:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(messages),
            "temperature": 0,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": {
                "name": tool.name, "description": tool.description,
                "parameters": tool.parameters,
            }} for tool in tools]
            if self.provider == "groq" and self.model.startswith("openai/gpt-oss-"):
                # Leave room for the tool call within the default completion budget.
                payload["reasoning_effort"] = "low"
        if self.provider == "openrouter":
            payload["provider"] = {"require_parameters": True}
        response = asyncio.run(self._post(payload, timeout_seconds))
        response.raise_for_status()
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Envelope inválido")
            if "error" in data:
                raise ProviderTransientError("O provedor rejeitou a geração.")
            message = data["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError("Mensagem inválida")
            calls = message.get("tool_calls") or []
            if calls:
                if len(calls) != 1:
                    raise ValueError("Esperada uma ferramenta por turno")
                function = calls[0]["function"]
                arguments = json.loads(function["arguments"])
                if not isinstance(arguments, dict) or not isinstance(function["name"], str):
                    raise ValueError("Argumentos inválidos")
                allowed = {tool.name for tool in tools}
                if function["name"] not in allowed:
                    raise ValueError("Ferramenta não solicitada")
                if function["name"] == "run_sql" and (
                    not isinstance(arguments.get("sql"), str) or not arguments["sql"].strip()
                ):
                    raise ValueError("SQL ausente ou inválido")
                return ModelTurn(tool_call=ToolCall(function["name"], arguments))
            answer = message.get("content")
            if isinstance(answer, str) and answer.strip():
                return ModelTurn(answer=answer)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderTransientError("O provedor retornou conteúdo inválido.") from exc
        raise ProviderTransientError("O provedor não retornou conteúdo utilizável.")

    async def _post(self, payload, timeout_seconds):
        # Um timeout total cancela a operação e fecha o transporte. O timeout
        # isolado do httpx limita fases de I/O, mas não a duração total da chamada.
        async with asyncio.timeout(timeout_seconds):
            async with (nullcontext(self.client) if self.client else httpx.AsyncClient()) as client:
                return await client.post(
                    self.endpoint, json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=timeout_seconds,
                )

    @staticmethod
    def _messages(messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        pending_id = None
        for index, message in enumerate(messages):
            role = message["role"]
            if role == "assistant" and "tool_call" in message:
                call = message["tool_call"]
                pending_id = f"call_{index}"
                result.append({"role": role, "content": None, "tool_calls": [{
                    "id": pending_id, "type": "function", "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                    },
                }]})
            elif role == "tool":
                if pending_id is None:
                    raise ValueError("Resultado sem chamada de ferramenta")
                result.append({"role": "tool", "tool_call_id": pending_id,
                               "content": message["content"]})
                pending_id = None
            else:
                result.append({"role": role, "content": message["content"]})
        return result
