"""Testes do ciclo de agente com modelo simulado."""

import sqlite3

import pytest

from app.agent import AgentError, AgentService
from app.agent_models import ModelTurn, ToolCall
from app.gold_database import EXPECTED_TABLES, GoldDatabase
from app.sql_executor import GoldQueryExecutor


def _create_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.execute("INSERT INTO dim_movies (id, title) VALUES (1, 'A')")


class FakeModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = turns
        self.calls: list[tuple[list[dict], tuple]] = []

    def complete(self, messages, tools):
        self.calls.append((list(messages), tuple(tools)))
        return self.turns.pop(0)


def test_agent_executes_one_tool_call_and_returns_rows(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [
            ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT id, title FROM dim_movies"})),
            ModelTurn(answer="Encontrei o filme A na camada Gold."),
        ]
    )

    response = AgentService(
        model,
        GoldQueryExecutor(GoldDatabase(database_path)),
    ).answer("Quais filmes existem?")

    assert response.answer == "Encontrei o filme A na camada Gold."
    assert response.rows == (({"id": 1, "title": "A"}),)
    assert response.tool_calls == 1
    assert len(model.calls) == 2
    assert model.calls[0][1][0].name == "run_sql"
    assert "dim_movies" in model.calls[0][0][0]["content"]
    assert "Q01" in model.calls[0][0][0]["content"]
    assert "Q14" in model.calls[0][0][0]["content"]


def test_agent_rejects_missing_tool_call(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel([ModelTurn(answer="Não sei.")])

    with pytest.raises(AgentError, match="não solicitou"):
        AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer("Oi")


def test_agent_rejects_second_tool_call(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [
            ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT id FROM dim_movies"})),
            ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT id FROM dim_movies"})),
        ]
    )

    with pytest.raises(AgentError, match="mais de uma"):
        AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer("Conte")
