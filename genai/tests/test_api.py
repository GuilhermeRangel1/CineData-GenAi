"""Testes do contrato operacional inicial."""

from fastapi.testclient import TestClient


def test_health_returns_process_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
