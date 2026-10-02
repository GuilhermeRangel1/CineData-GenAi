"""Testes dos limites de execução analítica do Gold."""

from app.gold_database import GoldDatabase
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql


def test_fact_metric_rankings_use_extended_query_timeout(tmp_path) -> None:
    executor = GoldQueryExecutor(
        GoldDatabase(tmp_path / "gold.db"),
        timeout_seconds=5,
        complex_timeout_seconds=15,
    )
    query = validate_sql(
        "SELECT popularidade FROM fact_movies_performance "
        "WHERE popularidade IS NOT NULL ORDER BY popularidade DESC LIMIT 3"
    )

    assert executor._timeout_for(query) == 15


def test_actor_director_pair_ranking_gets_its_own_timeout_budget(tmp_path) -> None:
    executor = GoldQueryExecutor(
        GoldDatabase(tmp_path / "gold.db"),
        timeout_seconds=5,
        complex_timeout_seconds=15,
        pair_query_timeout_seconds=45,
    )
    query = validate_sql(
        "WITH actor_links AS MATERIALIZED (SELECT sk_movie_id FROM bridge_movie_person), "
        "director_links AS MATERIALIZED (SELECT sk_movie_id FROM bridge_movie_person), "
        "pair_counts AS MATERIALIZED (SELECT COUNT(*) AS total FROM actor_links "
        "JOIN director_links USING (sk_movie_id)) SELECT total FROM pair_counts"
    )

    assert executor._timeout_for(query) == 45
