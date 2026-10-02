"""Testes do contrato operacional inicial."""

from fastapi.testclient import TestClient

from app.agent import AgentClarification
from app.agent_models import AgentResponse
from app.api import get_agent_service
from app.main import app


def test_health_returns_process_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_question_rejects_empty_question(client: TestClient) -> None:
    response = client.post("/api/v1/questions", json={"question": "  "})

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
