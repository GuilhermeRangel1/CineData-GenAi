"""Testes do contrato operacional inicial."""

from fastapi.testclient import TestClient

from app.agent import AgentClarification, AgentUnsupported
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
        def answer(self, question: str) -> AgentResponse:
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
        },
    }


def test_question_response_preserves_platform_source(client: TestClient) -> None:
    class PlatformAgent:
        def answer(self, question: str) -> AgentResponse:
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


def test_question_rejects_empty_question(client: TestClient) -> None:
    app.dependency_overrides[get_agent_service] = lambda: object()
    try:
        response = client.post("/api/v1/questions", json={"question": "  "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_question_returns_clarification_envelope(client: TestClient) -> None:
    class ClarifyingAgent:
        def answer(self, question: str) -> AgentResponse:
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
        def answer(self, question: str) -> AgentResponse:
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


def test_question_returns_query_timeout_envelope(client: TestClient) -> None:
    class TimingOutAgent:
        def answer(self, question: str) -> AgentResponse:
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
                "A consulta levou mais tempo que o limite. "
                "Tente uma pergunta mais específica."
            ),
            "details": None,
        },
    }
