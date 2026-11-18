"""Testes locais do adaptador Gemini sem chamadas externas."""

from types import SimpleNamespace

import pytest

from app.agent_models import ModelTurn, ToolCall
from app.complexity_router import QuestionComplexity
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


def test_timeout_budget_shared_with_internal_fallback(monkeypatch):
    import app.gemini_adapter as adapter

    times = iter([0, 0, 3])
    monkeypatch.setattr(adapter.time, "monotonic", lambda: next(times))
    response = SimpleNamespace(candidates=[], text="ok")
    client = FakeClient([TimeoutError(), response])
    model = GeminiToolCallingModel("key", client=client)
    assert model.complete_for_complexity([], [], QuestionComplexity.SIMPLE,
                                         timeout_seconds=5).answer == "ok"
    assert client.models.calls[0]["config"].http_options.timeout == 5000
    assert client.models.calls[1]["config"].http_options.timeout == 2000
    assert client.models.calls[0]["config"].http_options.retry_options.attempts == 1


def test_replay_tool_call_from_another_provider_uses_documented_signature_marker():
    history = GeminiToolCallingModel._contents([
        {"role": "assistant", "tool_call": {"name": "run_sql", "arguments": {"sql": "SELECT 1"}}},
        {"role": "tool", "name": "run_sql", "content": '{"rows":[{"value":1}]}'},
    ])
    assert history[0].parts[0].thought_signature == b"skip_thought_signature_validator"
    assert history[1].parts[0].function_response.response == {"rows": [{"value": 1}]}


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


def test_complex_route_falls_back_to_light_model_once() -> None:
    class RateLimitError(RuntimeError):
        status_code = 429

    client = FakeClient(
        [RateLimitError(), SimpleNamespace(candidates=[], text="Resposta pelo modelo leve")]
    )
    model = GeminiToolCallingModel("test-key", client=client)

    result = model.complete_for_complexity(
        [{"role": "user", "content": "Compare os filmes"}],
        [],
        QuestionComplexity.COMPLEX,
    )

    assert result == ModelTurn(answer="Resposta pelo modelo leve")
    assert [call["model"] for call in client.models.calls] == [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    ]
