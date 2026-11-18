"""Contrato HTTP compatível com OpenAI, sem chamadas externas."""

import asyncio
import json

import httpx
import pytest

from app.agent_models import ModelTurn, ToolCall, ToolDefinition
from app.errors import ProviderTransientError
from app.openai_adapter import OpenAICompatibleModel


def make_model(handler):
    return OpenAICompatibleModel(
        "groq", "secret", "test-model",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def test_tool_call_and_cross_provider_history():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {
            "tool_calls": [{"function": {
                "name": "run_sql", "arguments": '{"sql":"SELECT 1"}',
            }}],
        }}]})

    result = make_model(handler).complete([
        {"role": "user", "content": "Pergunta"},
        {"role": "assistant", "tool_call": {
            "name": "run_sql", "arguments": {"sql": "SELECT 1"},
            "thought_signature": b"gemini-only",
        }},
        {"role": "tool", "name": "run_sql", "content": '{"rows":[{"x":1}]}'},
    ], [ToolDefinition("run_sql", "Consulta", {"type": "object"})])
    assert result == ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT 1"}))
    messages = requests[0]["messages"]
    assert messages[1]["tool_calls"][0]["id"] == messages[2]["tool_call_id"]
    assert "thought_signature" not in json.dumps(requests[0])
    assert "parallel_tool_calls" not in requests[0]


@pytest.mark.parametrize("message", [
    None, {}, {"content": "   "},
    {"tool_calls": [{"function": {"name": "run_sql", "arguments": "bad"}}]},
    {"tool_calls": [{"function": {"name": "run_sql", "arguments": "[]"}}]},
])
def test_malformed_content_is_transient(message):
    model = make_model(lambda _: httpx.Response(200, json={"choices": [{"message": message}]}))
    with pytest.raises(ProviderTransientError):
        model.complete([{"role": "user", "content": "oi"}], [])


@pytest.mark.parametrize("arguments", ['{}', '{"sql":123}', '{"sql":"  "}'])
def test_invalid_sql_arguments_trigger_fallback_before_agent(arguments):
    model = make_model(lambda _: httpx.Response(200, json={"choices": [{"message": {
        "tool_calls": [{"function": {"name": "run_sql", "arguments": arguments}}],
    }}]}))
    with pytest.raises(ProviderTransientError):
        model.complete([], [ToolDefinition("run_sql", "Consulta", {"type": "object"})])


def test_http_status_preserved_for_router():
    model = make_model(lambda _: httpx.Response(429, json={"error": "quota"}))
    with pytest.raises(httpx.HTTPStatusError) as caught:
        model.complete([], [])
    assert caught.value.response.status_code == 429


def test_timeout_is_forwarded_and_openrouter_does_not_select_extra_models():
    def handler(request):
        assert request.extensions["timeout"]["read"] == 2
        payload = json.loads(request.content)
        assert payload["model"] == "chosen/model"
        assert "models" not in payload
        assert payload["provider"]["require_parameters"] is True
        return httpx.Response(200, json={"choices": [{"message": {"content": "Resposta"}}]})

    model = OpenAICompatibleModel("openrouter", "secret", "chosen/model",
                                  client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert model.complete_for_complexity([], [], None, timeout_seconds=2).answer == "Resposta"


def test_total_deadline_cancels_transport():
    cancelled = []

    async def slow_handler(request):
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.append(True)
        return httpx.Response(200, json={})

    model = make_model(slow_handler)
    with pytest.raises(TimeoutError):
        model.complete_for_complexity([], [], None, timeout_seconds=0.01)
    assert cancelled == [True]
