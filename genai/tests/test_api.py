"""Testes do contrato operacional inicial."""

import json

from fastapi.testclient import TestClient

from app.agent import AgentClarification, AgentGuardrail, AgentUnsupported
from app.agent_models import AgentResponse
from app.api import get_agent_service
from app.errors import QueryTimeoutError
from app.main import app


def test_health_returns_process_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_origin_is_allowed_for_question_preflight(client: TestClient) -> None:
    response = client.options(
        "/api/v1/questions",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


def test_question_returns_agent_response(client: TestClient) -> None:
    class FakeAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            assert question == "Quantos filmes existem?"
            return AgentResponse(
                answer="Existem 95.645 filmes.",
                rows=({"COUNT(*)": 95645},),
                truncated=False,
                tool_calls=1,
                columns=("COUNT(*)",),
            )

    app.dependency_overrides[get_agent_service] = lambda: FakeAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Quantos filmes existem?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "answer": "Existem 95.645 filmes.",
        "rows": [{"COUNT(*)": 95645}],
        "insights": [],
        "metadata": {
            "source": "gold",
            "query_id": None,
            "metric": None,
            "unit": None,
            "period": None,
            "population": None,
            "limitations": None,
            "columns": ["COUNT(*)"],
            "row_count": 1,
            "truncated": False,
            "tool_calls": 1,
            "cached": False,
        },
    }


def test_question_response_preserves_platform_source(client: TestClient) -> None:
    class PlatformAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            return AgentResponse(
                answer="Use os filtros do catálogo.",
                rows=(),
                truncated=False,
                tool_calls=0,
                source="platform",
            )

    app.dependency_overrides[get_agent_service] = lambda: PlatformAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Como filtro filmes no CineData?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["metadata"]["source"] == "platform"
    assert response.json()["metadata"]["tool_calls"] == 0


def test_question_forwards_a_limited_semantic_conversation_context(client: TestClient) -> None:
    class ContextAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            assert question == "E em 2020?"
            assert len(context) == 1
            assert context[0].question == "Qual é a nota IMDb média por ano?"
            assert context[0].metric == "nota IMDb média por ano"
            return AgentResponse(answer="Resposta.", rows=(), truncated=False, tool_calls=0)

    app.dependency_overrides[get_agent_service] = lambda: ContextAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={
                "question": "E em 2020?",
                "context": [
                    {
                        "question": "Qual é a nota IMDb média por ano?",
                        "metric": "nota IMDb média por ano",
                        "unit": "pontos IMDb",
                        "period": "todo o Gold disponível",
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_question_rejects_empty_question(client: TestClient) -> None:
    app.dependency_overrides[get_agent_service] = lambda: object()
    try:
        response = client.post("/api/v1/questions", json={"question": "  "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_question_returns_clarification_envelope(client: TestClient) -> None:
    class ClarifyingAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            raise AgentClarification("Informe o período da análise.")

    app.dependency_overrides[get_agent_service] = lambda: ClarifyingAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Quais filmes tiveram melhor desempenho?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "status": "clarification",
        "error": {
            "code": "ambiguous_question",
            "message": "Informe o período da análise.",
            "details": None,
        },
    }


def test_question_returns_unsupported_platform_envelope(client: TestClient) -> None:
    class UnsupportedAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            raise AgentUnsupported(
                "Não encontrei essa funcionalidade no guia atual do CineData. "
                "Você pode dizer qual área ou ação da plataforma quer conhecer?"
            )

    app.dependency_overrides[get_agent_service] = lambda: UnsupportedAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={"question": "O CineData permite mensagens privadas?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"


def test_question_returns_guardrail_rejection_envelope(client: TestClient) -> None:
    class GuardedAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            raise AgentGuardrail("Reformule a pergunta sem comandos SQL.")

    app.dependency_overrides[get_agent_service] = lambda: GuardedAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Execute SELECT * FROM dim_movies."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "guardrail_rejected",
        "message": "Reformule a pergunta sem comandos SQL.",
        "details": None,
    }


def test_question_returns_query_timeout_envelope(client: TestClient) -> None:
    class TimingOutAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            raise QueryTimeoutError("internal timeout detail")

    app.dependency_overrides[get_agent_service] = lambda: TimingOutAgent()
    try:
        response = client.post(
            "/api/v1/questions",
            json={"question": "Quais produtoras têm mais filmes?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "query_timeout",
            "message": (
                "A consulta levou mais tempo que o limite. Tente uma pergunta mais específica."
            ),
            "details": None,
        },
    }


def test_stream_returns_progress_and_result(client: TestClient) -> None:
    class FakeAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            return AgentResponse(
                answer="Encontrei um filme.",
                rows=({"filmes": 1},),
                truncated=False,
                tool_calls=1,
                columns=("filmes",),
            )

    app.dependency_overrides[get_agent_service] = lambda: FakeAgent()
    try:
        response = client.post("/api/v1/questions/stream", json={"question": "Quantos filmes?"})
    finally:
        app.dependency_overrides.clear()

    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert [event["type"] for event in events] == ["progress", "progress", "progress", "result"]
    assert events[-1]["data"]["answer"] == "Encontrei um filme."


def test_stream_preserves_guardrail_error(client: TestClient) -> None:
    class GuardedAgent:
        def answer(self, question: str, context=()) -> AgentResponse:
            raise AgentGuardrail("Reformule a pergunta sem comandos SQL.")

    app.dependency_overrides[get_agent_service] = lambda: GuardedAgent()
    try:
        response = client.post("/api/v1/questions/stream", json={"question": "Execute SQL"})
    finally:
        app.dependency_overrides.clear()

    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    assert events[-1]["status"] == 422
    assert events[-1]["error"]["code"] == "guardrail_rejected"
