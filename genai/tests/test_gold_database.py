"""Testes determinísticos da abertura e validação do Gold."""

import sqlite3

import pytest

from app.errors import GoldInvalidError, GoldUnavailableError
from app.gold_database import EXPECTED_TABLES, GoldDatabase


def _create_gold_fixture(path) -> None:
    with sqlite3.connect(path) as connection:
        for table in EXPECTED_TABLES:
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER)')


def test_check_readiness_accepts_expected_schema(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)

    readiness = GoldDatabase(database_path).check_readiness()

    assert readiness.path == database_path.resolve()
    assert readiness.tables == EXPECTED_TABLES


def test_connection_is_read_only(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    _create_gold_fixture(database_path)

    with (
        GoldDatabase(database_path).connect() as connection,
        pytest.raises(sqlite3.OperationalError),
    ):
        connection.execute("CREATE TABLE forbidden (id INTEGER)")


def test_missing_database_has_controlled_error(tmp_path) -> None:
    with pytest.raises(GoldUnavailableError):
        GoldDatabase(tmp_path / "missing.db").check_readiness()


def test_lfs_pointer_has_controlled_error(tmp_path) -> None:
    pointer = tmp_path / "gold.db"
    pointer.write_text("version https://git-lfs.github.com/spec/v1\n", encoding="utf-8")

    with pytest.raises(GoldUnavailableError):
        GoldDatabase(pointer).check_readiness()


def test_schema_without_expected_table_is_invalid(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE dim_movies (id INTEGER)")

    with pytest.raises(GoldInvalidError):
        GoldDatabase(database_path).check_readiness()
