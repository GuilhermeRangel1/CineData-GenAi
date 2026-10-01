"""Testes do contrato operacional inicial."""

from fastapi.testclient import TestClient

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
        "answer": "Existem 95.645 filmes.",
        "rows": [{"COUNT(*)": 95645}],
        "truncated": False,
        "tool_calls": 1,
    }


def test_question_rejects_empty_question(client: TestClient) -> None:
    response = client.post("/api/v1/questions", json={"question": "  "})

    assert response.status_code == 422
