"""Testes do ciclo de agente com modelo simulado."""

import sqlite3
from datetime import date, timedelta

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


def _create_popularity_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES - {"dim_movies", "fact_movies_performance"}:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.execute("CREATE TABLE dim_movies (sk_movie_id TEXT, titulo TEXT)")
        connection.execute(
            "CREATE TABLE fact_movies_performance (sk_movie_id TEXT, popularidade REAL)"
        )
        movies = (
            ("id-1", "X high", 9.0),
            ("id-2", "Z tie", 8.0),
            ("id-3", "A tie", 8.0),
            ("id-4", "lower", 7.0),
        )
        connection.executemany(
            "INSERT INTO dim_movies VALUES (?, ?)",
            ((movie_id, title) for movie_id, title, _ in movies),
        )
        connection.executemany(
            "INSERT INTO fact_movies_performance VALUES (?, ?)",
            ((movie_id, popularity) for movie_id, _, popularity in movies),
        )


def _create_director_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES - {
            "dim_people", "bridge_movie_person", "fact_movies_performance"
        }:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.execute(
            "CREATE TABLE dim_people (sk_person_id TEXT, nome_pessoa TEXT, tipo_pessoa TEXT)"
        )
        connection.execute(
            "CREATE TABLE bridge_movie_person (sk_movie_id TEXT, sk_person_id TEXT, "
            "PRIMARY KEY (sk_movie_id, sk_person_id))"
        )
        connection.execute(
            "CREATE TABLE fact_movies_performance (sk_movie_id TEXT PRIMARY KEY, "
            "nota_imdb REAL, qtd_imdb INTEGER)"
        )
        people = (("p1", "Diretor A", "Diretor"), ("p2", "Diretor B", "Diretor"),
                 ("p3", "Diretor C", "Diretor"))
        connection.executemany("INSERT INTO dim_people VALUES (?, ?, ?)", people)
        credits = []
        performances = []
        for person_id, rating in (("p1", 9.0), ("p2", 9.0), ("p3", 8.0)):
            for number in range(5):
                movie_id = f"{person_id}-movie-{number}"
                credits.append((movie_id, person_id))
                performances.append((movie_id, rating, 100))
        connection.executemany("INSERT INTO bridge_movie_person VALUES (?, ?)", credits)
        connection.executemany(
            "INSERT INTO fact_movies_performance VALUES (?, ?, ?)", performances
        )


def _create_actor_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES - {"dim_people", "bridge_movie_person"}:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.execute(
            "CREATE TABLE dim_people (sk_person_id TEXT, nome_pessoa TEXT, tipo_pessoa TEXT)"
        )
        connection.execute(
            "CREATE TABLE bridge_movie_person (sk_movie_id TEXT, sk_person_id TEXT, "
            "PRIMARY KEY (sk_movie_id, sk_person_id))"
        )
        people = (("p1", "Ator A", "Ator"), ("p2", "Ator B", "Ator"),
                  ("p3", "Ator C", "Ator"), ("p4", "Diretor", "Diretor"))
        connection.executemany("INSERT INTO dim_people VALUES (?, ?, ?)", people)
        credits = [(f"movie-{i}", "p1") for i in range(3)]
        credits += [(f"movie-{i}", "p2") for i in range(3)]
        credits += [("movie-0", "p3"), ("movie-1", "p3"), ("movie-0", "p4")]
        connection.executemany("INSERT INTO bridge_movie_person VALUES (?, ?)", credits)


def _create_actor_director_gold_fixture(path) -> None:
    recent_date = (date.today() - timedelta(days=365)).isoformat()
    old_date = (date.today() - timedelta(days=6 * 365)).isoformat()
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES - {"dim_movies", "dim_people", "bridge_movie_person"}:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.execute(
            "CREATE TABLE dim_movies (sk_movie_id TEXT PRIMARY KEY, data_lancamento TEXT)"
        )
        connection.execute(
            "CREATE TABLE dim_people (sk_person_id TEXT PRIMARY KEY, nome_pessoa TEXT, "
            "tipo_pessoa TEXT)"
        )
        connection.execute(
            "CREATE TABLE bridge_movie_person (sk_movie_id TEXT, sk_person_id TEXT, "
            "PRIMARY KEY (sk_movie_id, sk_person_id))"
        )
        connection.executemany(
            "INSERT INTO dim_people VALUES (?, ?, ?)",
            (("a1", "Ator A", "Ator"), ("a2", "Ator B", "Ator"),
             ("d1", "Diretor A", "Diretor"), ("d2", "Diretor B", "Diretor")),
        )
        connection.executemany(
            "INSERT INTO dim_movies VALUES (?, ?)",
            (("recent-1", recent_date), ("recent-2", recent_date),
             ("recent-3", recent_date), ("old", old_date)),
        )
        connection.executemany(
            "INSERT INTO bridge_movie_person VALUES (?, ?)",
            (("recent-1", "a1"), ("recent-1", "d1"),
             ("recent-2", "a1"), ("recent-2", "d1"),
             ("recent-3", "a2"), ("recent-3", "d2"),
             ("old", "a1"), ("old", "d1")),
        )


def _create_company_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES - {
            "dim_companies", "bridge_movie_company", "fact_movies_performance"
        }:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.execute(
            "CREATE TABLE dim_companies (sk_company_id TEXT, nome_produtora TEXT)"
        )
        connection.execute(
            "CREATE TABLE bridge_movie_company (sk_movie_id TEXT, sk_company_id TEXT, "
            "PRIMARY KEY (sk_movie_id, sk_company_id))"
        )
        connection.execute(
            "CREATE TABLE fact_movies_performance (sk_movie_id TEXT PRIMARY KEY, "
            "receita_brl REAL, orcamento_brl REAL, lucro_brl REAL)"
        )
        connection.executemany(
            "INSERT INTO dim_companies VALUES (?, ?)",
            (("c1", "Produtora A"), ("c2", "Produtora B"), ("c3", "Produtora C")),
        )
        connection.executemany(
            "INSERT INTO bridge_movie_company VALUES (?, ?)",
            (("m1", "c1"), ("m2", "c2"), ("m3", "c3"),
             ("m4", "c1"), ("m5", "c1"), ("m6", "c2")),
        )
        connection.executemany(
            "INSERT INTO fact_movies_performance VALUES (?, ?, ?, ?)",
            (("m1", 100.0, 40.0, 60.0), ("m2", 120.0, 60.0, 60.0),
             ("m3", 1_000_000.0, None, None)),
        )


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
        ]
    )

    response = AgentService(
        model,
        GoldQueryExecutor(GoldDatabase(database_path)),
    ).answer("Quais filmes existem?")

    assert response.answer == "A consulta retornou 1 resultado; os valores estão na tabela."
    assert response.rows == (({"id": 1, "title": "A"}),)
    assert response.tool_calls == 1
    assert len(model.calls) == 1
    assert model.calls[0][1][0].name == "run_sql"
    assert "dim_movies" in model.calls[0][0][0]["content"]
    assert "Q01" in model.calls[0][0][0]["content"]
    assert "Q14" in model.calls[0][0][0]["content"]
    assert "peça esclarecimento começando por CLARIFY:" in model.calls[0][0][0]["content"]
    assert "População válida" in model.calls[0][0][0]["content"]
    assert "receita por filme" in model.calls[0][0][0]["content"]
    assert "mais bem avaliado pelo IMDb" in model.calls[0][0][0]["content"]
    assert "nunca como a quantidade qtd_imdb" in model.calls[0][0][0]["content"]


def test_platform_question_uses_guide_without_model_or_sql(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Como faço para filtrar filmes por gênero no CineData?")

    assert response.source == "platform"
    assert response.rows == ()
    assert response.tool_calls == 0
    assert "Filtros avançados" in response.answer
    assert "gênero" in response.answer
    assert model.calls == []


def test_mixed_question_uses_guide_and_gold_sources(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT COUNT(*) AS total FROM dim_movies"}))]
    )

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Como faço para encontrar filmes no CineData e quantos filmes há no catálogo?")

    assert response.source == "mixed"
    assert response.rows == (({"total": 1}),)
    assert response.tool_calls == 1
    assert "Orientação sobre o CineData" in response.answer
    assert "Análise dos filmes (Gold)" in response.answer
    assert len(model.calls) == 1


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


def test_simple_most_viewed_question_uses_fast_popularity_query_and_keeps_ties(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_popularity_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model,
        GoldQueryExecutor(GoldDatabase(database_path)),
    ).answer("Quais os três filmes mais vistos?")

    assert model.calls == []
    assert [row["titulo"] for row in response.rows] == ["X high", "A tie", "Z tie"]
    assert response.query_id == "Q04"
    assert response.metric == "popularidade por filme"
    assert "não contagem real de visualizações" in response.limitations


def test_popularity_fast_path_does_not_discard_unhandled_filters(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    model = FakeModel(
        [ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT id FROM dim_movies"}))]
    )

    AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Quais os três filmes mais vistos do Nolan?"
    )

    assert len(model.calls) == 1


def test_director_average_question_uses_single_aggregate_and_returns_top_ties(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_director_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer(
        "Quais diretores têm a maior média de nota IMDb entre aqueles com pelo menos "
        "cinco filmes, considerando todo o Gold disponível?"
    )

    assert model.calls == []
    assert [row["nome_pessoa"] for row in response.rows] == ["Diretor A", "Diretor B"]
    assert all(row["nota_media"] == 9.0 for row in response.rows)
    assert response.query_id == "Q08"


def test_director_average_fast_path_does_not_discard_user_filter(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_director_gold_fixture(database_path)
    model = FakeModel(
        [ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT sk_person_id, "
         "nome_pessoa, 5 AS filmes_validos, 9.0 AS nota_media FROM dim_people"}))]
    )

    AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Quais diretores têm a maior média de nota IMDb com nome Nolan?"
    )

    assert len(model.calls) == 1


def test_all_time_actor_ranking_uses_single_aggregate_and_returns_ties(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_actor_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Quais atores participaram de mais filmes?")

    assert model.calls == []
    assert [row["nome_pessoa"] for row in response.rows] == ["Ator A", "Ator B"]
    assert all(row["total_filmes"] == 3 for row in response.rows)
    assert response.query_id is None
    assert response.period == "todo o Gold disponível"


def test_all_time_actor_ranking_does_not_discard_period_or_name_filter(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_actor_gold_fixture(database_path)
    model = FakeModel(
        [ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT sk_person_id, "
         "nome_pessoa, 1 AS total_filmes FROM dim_people"}))]
    )

    AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Quais atores participaram de mais filmes nos últimos cinco anos?"
    )
    AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Quais atores participaram de mais filmes do Nolan?"
    )

    assert len(model.calls) == 2


def test_five_year_actor_ranking_uses_exact_date_window(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_actor_director_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Qual ator participou de mais filmes nos últimos cinco anos?")

    assert model.calls == []
    assert [row["nome_pessoa"] for row in response.rows] == ["Ator A"]
    assert response.rows[0]["total_filmes"] == 2
    assert response.query_id == "Q07"


def test_actor_director_pair_ranking_aggregates_ids_before_names(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_actor_director_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Qual dupla de ator e diretor trabalhou junta em mais filmes?")

    assert model.calls == []
    assert response.rows == (
        {"ator": "Ator A", "diretor": "Diretor A", "filmes_em_comum": 3},
    )
    assert response.query_id == "Q09"


def test_top_company_profit_uses_valid_population_once_and_keeps_ties(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_company_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Qual produtora acumulou o maior lucro total em BRL?")

    assert model.calls == []
    assert [row["nome_produtora"] for row in response.rows] == [
        "Produtora A", "Produtora B"
    ]
    assert all(row["lucro_total_brl"] == 60.0 for row in response.rows)
    assert response.query_id == "Q11"


def test_top_company_profit_does_not_discard_filters(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_company_gold_fixture(database_path)
    model = FakeModel(
        [ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT sk_company_id, "
         "nome_produtora, 1 AS filmes_elegiveis, 1 AS lucro_total_brl "
         "FROM dim_companies"}))]
    )

    AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Qual produtora acumulou o maior lucro total em BRL do Nolan?"
    )

    assert len(model.calls) == 1


def test_top_company_movie_count_uses_single_bridge_scan_and_respects_n(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_company_gold_fixture(database_path)
    model = FakeModel([])

    response = AgentService(
        model, GoldQueryExecutor(GoldDatabase(database_path))
    ).answer("Quais as 2 produtoras com mais filmes?")

    assert model.calls == []
    assert [row["nome_produtora"] for row in response.rows] == [
        "Produtora A", "Produtora B"
    ]
    assert [row["total_filmes"] for row in response.rows] == [3, 2]
    assert response.metric == "quantidade de filmes por produtora"


def test_top_company_movie_count_does_not_discard_filters(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_company_gold_fixture(database_path)
    model = FakeModel(
        [ModelTurn(tool_call=ToolCall("run_sql", {"sql": "SELECT sk_company_id, "
         "nome_produtora, 1 AS total_filmes FROM dim_companies"}))]
    )

    AgentService(model, GoldQueryExecutor(GoldDatabase(database_path))).answer(
        "Quais as 10 produtoras com mais filmes de terror?"
    )

    assert len(model.calls) == 1


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
