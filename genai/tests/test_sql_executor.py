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
        "WITH cast_credits AS (SELECT sk_movie_id, sk_person_id FROM bridge_movie_person "
        "JOIN dim_people USING (sk_person_id) WHERE tipo_pessoa = 'Ator'), "
        "crew_credits AS (SELECT sk_movie_id, sk_person_id FROM bridge_movie_person "
        "JOIN dim_people USING (sk_person_id) WHERE 'Diretor' = tipo_pessoa) "
        "SELECT a.sk_person_id, d.sk_person_id, COUNT(*) AS total "
        "FROM cast_credits a JOIN crew_credits d USING (sk_movie_id) "
        "GROUP BY a.sk_person_id, d.sk_person_id"
    )

    assert executor._timeout_for(query) == 45

    one_role = validate_sql(
        "SELECT p.sk_person_id, COUNT(*) FROM bridge_movie_person b "
        "JOIN dim_people p USING (sk_person_id) WHERE p.tipo_pessoa = 'Ator' "
        "GROUP BY p.sk_person_id"
    )
    assert executor._timeout_for(one_role) == 15

    single_director_group = validate_sql(
        "WITH films AS (SELECT sk_movie_id FROM bridge_movie_person "
        "JOIN dim_people USING (sk_person_id) WHERE tipo_pessoa = 'Ator') "
        "SELECT p.sk_person_id, p.nome_pessoa, COUNT(*) FROM films "
        "JOIN bridge_movie_person b USING (sk_movie_id) "
        "JOIN dim_people p USING (sk_person_id) WHERE p.tipo_pessoa = 'Diretor' "
        "GROUP BY p.sk_person_id, p.nome_pessoa"
    )
    assert executor._timeout_for(single_director_group) == 15
