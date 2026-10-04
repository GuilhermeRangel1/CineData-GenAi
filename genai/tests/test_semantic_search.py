"""Testes do índice local de sinopses sem provedor externo."""

import sqlite3

import pytest

from app.errors import GoldUnavailableError
from app.gold_database import GoldDatabase
from app.semantic_search import SynopsisSearchIndex


def test_synopsis_index_finds_movies_by_descriptive_terms(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE dim_movies (sk_movie_id TEXT, titulo TEXT, sinopse TEXT)")
        connection.executemany(
            "INSERT INTO dim_movies VALUES (?, ?, ?)",
            (
                ("m1", "Horizonte", "Uma astronauta investiga um sinal extraterrestre no espaço."),
                ("m2", "Casa", "Uma família encontra uma casa antiga no interior."),
            ),
        )

    results = SynopsisSearchIndex(GoldDatabase(database_path)).search(
        "filmes sobre astronauta no espaço"
    )

    assert [result.movie_id for result in results] == ["m1"]
    assert results[0].title == "Horizonte"


def test_synopsis_index_rebuilds_after_gold_catalog_changes(tmp_path) -> None:
    database_path = tmp_path / "gold.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE dim_movies (sk_movie_id TEXT, titulo TEXT, sinopse TEXT)")
        connection.execute(
            "INSERT INTO dim_movies VALUES ('m1', 'Horizonte', 'Uma viagem pelo espaço.')"
        )

    index = SynopsisSearchIndex(GoldDatabase(database_path))
    assert [result.title for result in index.search("viagem espacial")] == ["Horizonte"]

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO dim_movies VALUES "
            "('m2', 'Pistas', 'Uma detetive resolve crimes em uma cidade pequena.')"
        )

    results = index.search("detetive resolve crimes")

    assert [result.movie_id for result in results] == ["m2"]


def test_synopsis_index_reports_missing_database_as_service_error(tmp_path) -> None:
    index = SynopsisSearchIndex(GoldDatabase(tmp_path / "missing.db"))

    with pytest.raises(GoldUnavailableError):
        index.search("filmes sobre astronautas")
