"""Testes da validação SQL e dos limites de execução."""

import sqlite3

import pytest

from app.errors import QueryExecutionError, SqlValidationError
from app.gold_database import EXPECTED_TABLES, GoldDatabase
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql


def _create_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER, title TEXT)')
        connection.executemany(
            "INSERT INTO dim_movies (id, title) VALUES (?, ?)",
            [(1, "A"), (2, "B"), (3, "C")],
        )


def test_validate_select_and_apply_default_limit() -> None:
    query = validate_sql("SELECT id, title FROM dim_movies", max_rows=2)

    assert query.tables == frozenset({"dim_movies"})
    assert query.sql.endswith("LIMIT 2")


def test_validate_normalizes_accents_only_in_gold_column_identifiers() -> None:
    query = validate_sql(
        "SELECT f.orçamento_brl FROM fact_movies_performance AS f",
    )

    assert "orcamento_brl" in query.sql
    assert "orçamento_brl" not in query.sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM dim_movies",
        "DROP TABLE dim_movies",
        "PRAGMA journal_mode",
        "SELECT * FROM dim_movies; SELECT * FROM dim_people",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM dim_movies JOIN other_table ON 1 = 1",
    ],
)
def test_validate_rejects_unsafe_or_unknown_sql(sql: str) -> None:
    with pytest.raises(SqlValidationError):
        validate_sql(sql)


def test_validate_caps_explicit_limit() -> None:
    query = validate_sql("SELECT * FROM dim_movies LIMIT 999", max_rows=2)

    assert query.sql.endswith("LIMIT 2")


@pytest.mark.parametrize(
    "sql",
    (
        "WITH RECURSIVE numbers(value) AS "
        "(SELECT 1 UNION ALL SELECT value + 1 FROM numbers) "
        "SELECT value FROM numbers",
        "SELECT left_table.id FROM dim_movies AS left_table CROSS JOIN dim_people AS right_table",
        "SELECT randomblob(1000000) FROM dim_movies",
    ),
)
def test_validate_rejects_costly_or_unsafe_query_shapes(sql: str) -> None:
    with pytest.raises(SqlValidationError):
        validate_sql(sql)


def test_executor_returns_rows_and_truncation(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    query = validate_sql("SELECT id, title FROM dim_movies", max_rows=2)

    result = GoldQueryExecutor(GoldDatabase(database_path), max_rows=2).execute(query)

    assert result.columns == ("id", "title")
    assert result.rows == (({"id": 1, "title": "A"}), ({"id": 2, "title": "B"}))
    assert result.truncated is False


def test_executor_denies_write_even_if_bypassing_guard(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    query = validate_sql("SELECT id FROM dim_movies")
    unsafe = query.__class__(sql="INSERT INTO dim_movies VALUES (4, 'D')", tables=query.tables)

    with pytest.raises(QueryExecutionError):
        GoldQueryExecutor(GoldDatabase(database_path)).execute(unsafe)


def test_executor_denies_read_outside_allowlist_even_if_bypassing_guard(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)
    unsafe = validate_sql("SELECT id FROM dim_movies")
    unsafe = unsafe.__class__(sql="SELECT name FROM sqlite_master", tables=unsafe.tables)

    with pytest.raises(QueryExecutionError):
        GoldQueryExecutor(GoldDatabase(database_path)).execute(unsafe)
