"""Smoke test real pode ser ensaiado sem credenciais nem rede."""

import pytest

from app.agent_models import ModelTurn, ToolCall
from app.config import Settings
from app.provider_check import check_provider_chain
from app.provider_router import ProviderRouter
from app.sql_executor import QueryResult


def test_check_rejects_unconfigured_routes_before_network():
    with pytest.raises(ValueError, match="groq"):
        check_provider_chain(Settings(_env_file=None, gemini_api_key=""), "groq", [])


def test_real_check_uses_model_tool_call_and_compares_local_result(monkeypatch):
    import app.provider_check as module

    class Model:
        model = "test"

        def complete_for_complexity(self, *args, **kwargs):
            return ModelTurn(tool_call=ToolCall(
                "run_sql", {"sql": "SELECT COUNT(*) AS total FROM dim_movies"},
            ))

    class Executor:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, query):
            assert "dim_movies" in query.sql
            return QueryResult(("total",), ({"total": 7},), False)

    router = ProviderRouter([("groq", Model())])
    monkeypatch.setattr(module, "build_provider_router", lambda _: router)
    monkeypatch.setattr(module, "GoldQueryExecutor", Executor)
    settings = Settings(_env_file=None, groq_api_key="private", groq_model="test")
    report = check_provider_chain(settings, "groq", [])
    assert report["provider"] == "groq"
    assert report["total_movies"] == 7
    assert "private" not in str(report)


def test_simulated_failure_routes_to_real_alternative(monkeypatch):
    import app.provider_check as module

    class Model:
        model = "test"

        def complete_for_complexity(self, *args, **kwargs):
            return ModelTurn(tool_call=ToolCall(
                "run_sql", {"sql": "SELECT COUNT(*) AS total FROM dim_movies"},
            ))

    class Executor:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, query):
            return QueryResult(("total",), ({"total": 7},), False)

    monkeypatch.setattr(module, "build_provider_router", lambda _: ProviderRouter([
        ("gemini", Model()), ("groq", Model()),
    ]))
    monkeypatch.setattr(module, "GoldQueryExecutor", Executor)
    settings = Settings(_env_file=None, gemini_api_key="key", groq_api_key="key", groq_model="m")
    report = check_provider_chain(settings, "gemini,groq", ["gemini"])
    assert report["provider"] == "groq"
