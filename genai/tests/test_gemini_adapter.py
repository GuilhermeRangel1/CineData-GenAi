"""Testes locais do adaptador Gemini sem chamadas externas."""

from types import SimpleNamespace

import pytest

from app.agent_models import ModelTurn, ToolCall
from app.errors import ProviderConfigurationError
from app.gemini_adapter import GeminiToolCallingModel


class FakeModels:
    def __init__(self, response) -> None:
        self.responses = list(response) if isinstance(response, list) else [response]
        self.kwargs = None
        self.calls = []

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, response) -> None:
        self.models = FakeModels(response)


def test_adapter_requires_api_key_without_injected_client() -> None:
    with pytest.raises(ProviderConfigurationError):
        GeminiToolCallingModel(None)


def test_adapter_normalizes_function_call_without_network() -> None:
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            function_call=SimpleNamespace(
                                name="run_sql",
                                args={"sql": "SELECT 1"},
                            ),
                            thought_signature=b"signature",
                        )
                    ]
                )
            )
        ],
        text=None,
    )
    client = FakeClient(response)
    model = GeminiToolCallingModel("test-key", client=client)

    result = model.complete(
        [{"role": "user", "content": "Conte os filmes"}],
        [],
    )

    assert result == ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT 1"}, b"signature"))
    assert client.models.kwargs["model"] == "gemini-3.5-flash-lite"
    assert "tools" not in client.models.kwargs["config"].model_dump(exclude_none=True)

    contents = model._contents(
        [
            {
                "role": "assistant",
                "tool_call": {
                    "name": "run_sql",
                    "arguments": {"sql": "SELECT 1"},
                    "thought_signature": b"signature",
                },
            }
        ]
    )
    assert contents[0].parts[0].thought_signature == b"signature"


def test_adapter_normalizes_final_text_without_network() -> None:
    response = SimpleNamespace(candidates=[], text="Resposta final")
    model = GeminiToolCallingModel("test-key", client=FakeClient(response))

    result = model.complete(
        [{"role": "user", "content": "Conte os filmes"}],
        [],
    )

    assert result == ModelTurn(answer="Resposta final")


def test_adapter_uses_fallback_once_for_a_retryable_provider_failure() -> None:
    class RateLimitError(RuntimeError):
        status_code = 429

    response = SimpleNamespace(candidates=[], text="Resposta pelo fallback")
    client = FakeClient([RateLimitError(), response])
    model = GeminiToolCallingModel(
        "test-key",
        model="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash",
        client=client,
    )

    result = model.complete([{"role": "user", "content": "Conte os filmes"}], [])

    assert result == ModelTurn(answer="Resposta pelo fallback")
    assert [call["model"] for call in client.models.calls] == [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
    ]


def test_adapter_does_not_fallback_for_non_retryable_provider_failure() -> None:
    client = FakeClient(ValueError("pedido inválido"))
    model = GeminiToolCallingModel("test-key", client=client)

    with pytest.raises(ValueError, match="pedido inválido"):
        model.complete([{"role": "user", "content": "Conte os filmes"}], [])

    assert len(client.models.calls) == 1
