"""Fixtures compartilhadas pelos testes da API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP local sem servidor ou chamadas externas."""

    return TestClient(app)
