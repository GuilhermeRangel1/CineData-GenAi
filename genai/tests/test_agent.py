"""Testes do ciclo de agente com modelo simulado."""

import sqlite3

import pytest

from app.agent import AgentClarification, AgentError, AgentService
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
    assert "somente números, nomes e conclusões sustentados" in model.calls[0][0][0]["content"]
    assert "População válida" in model.calls[0][0][0]["content"]
    assert "receita por filme" in model.calls[0][0][0]["content"]
    assert "mais bem avaliado pelo IMDb" in model.calls[0][0][0]["content"]
    assert "nunca como a quantidade qtd_imdb" in model.calls[0][0][0]["content"]


def test_agent_attaches_case_metadata_and_validates_columns(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [
            ModelTurn(
                tool_call=ToolCall(
                    "run_sql",
                    {
                        "sql": (
                            "SELECT id AS sk_movie_id, title AS titulo, "
                            "10.0 AS receita_brl FROM dim_movies"
                        )
                    },
                )
            ),
            ModelTurn(
                answer=(
                    "Resposta: O filme A tem receita de R$ 10,00.\n"
                    "Métrica: receita por filme\n"
                    "Unidade: BRL\n"
                    "Período: todo o Gold disponível\n"
                    "População válida: filmes com receita_brl não nula\n"
                    "Limitações: nenhuma adicional."
                )
            ),
        ]
    )

    response = AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Quais são os 10 filmes com maior receita em BRL?"
    )

    assert response.query_id == "Q01"
    assert response.columns == ("sk_movie_id", "titulo", "receita_brl")
    assert response.metric == "receita por filme"
    assert response.unit == "BRL"
    assert response.period == "todo o Gold disponível"


def test_agent_rejects_mismatched_columns_for_known_case(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [
            ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT id FROM dim_movies"})),
        ]
    )

    with pytest.raises(AgentError, match="colunas obrigatórias"):
        AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
            "Quais são os 10 filmes com maior receita em BRL?"
        )


def test_agent_rejects_known_case_without_semantic_response_fields(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [
            ModelTurn(
                tool_call=ToolCall(
                    "run_sql",
                    {
                        "sql": (
                            "SELECT id AS sk_movie_id, title AS titulo, "
                            "10.0 AS receita_brl FROM dim_movies"
                        )
                    },
                )
            ),
            ModelTurn(answer="O filme A tem receita de R$ 10,00."),
        ]
    )

    with pytest.raises(AgentError, match="campos obrigatórios"):
        AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
            "Quais são os 10 filmes com maior receita em BRL?"
        )


def test_agent_returns_controlled_clarification_without_query(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel([ModelTurn(answer="CLARIFY: Informe o período da análise.")])

    with pytest.raises(AgentClarification, match="Informe o período"):
        AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
            "Quais filmes tiveram melhor desempenho?"
        )


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
