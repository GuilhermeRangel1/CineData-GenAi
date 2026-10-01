from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.db.gold_seed import GoldDatabaseError, seed_from_gold_database

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


def _create_gold_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE dim_companies (sk_company_id TEXT PRIMARY KEY, nome_produtora TEXT);
        CREATE TABLE dim_genres (sk_genre_id TEXT PRIMARY KEY, nome_genero TEXT);
        CREATE TABLE dim_movies (
            sk_movie_id TEXT PRIMARY KEY, id_filme TEXT, titulo TEXT,
            data_lancamento TEXT, ano_lancamento INTEGER, duracao_minutos INTEGER,
            idioma_original TEXT, status_filme TEXT, sinopse TEXT,
            url_poster TEXT, url_backdrop TEXT
        );
        CREATE TABLE dim_people (
            sk_person_id TEXT PRIMARY KEY, nome_pessoa TEXT, tipo_pessoa TEXT
        );
        CREATE TABLE fact_movies_performance (
            sk_movie_id TEXT PRIMARY KEY, orcamento_usd NUMERIC, receita_usd NUMERIC,
            lucro_usd NUMERIC, orcamento_brl NUMERIC, receita_brl NUMERIC,
            lucro_brl NUMERIC, popularidade REAL, nota_tmdb REAL, qtd_tmdb INTEGER,
            nota_imdb REAL, qtd_imdb INTEGER
        );
        CREATE TABLE dim_reviews (
            sk_review_id TEXT PRIMARY KEY, sk_movie_id TEXT, qtd_avaliacoes_usuarios INTEGER,
            nota_media_usuarios REAL
        );
        CREATE TABLE movie_reviews (
            id INTEGER PRIMARY KEY, sk_movie_review_id TEXT, sk_movie_id TEXT,
            name TEXT, rating REAL, text TEXT, created_at TEXT
        );
        CREATE TABLE bridge_movie_company (sk_movie_id TEXT, sk_company_id TEXT);
        CREATE TABLE bridge_movie_genre (sk_movie_id TEXT, sk_genre_id TEXT);
        CREATE TABLE bridge_movie_person (sk_movie_id TEXT, sk_person_id TEXT);

        INSERT INTO dim_companies VALUES ('c1', 'Studio Example');
        INSERT INTO dim_genres VALUES ('g1', 'Drama');
        INSERT INTO dim_movies VALUES (
            'm1', '100', 'Old Title', '2024-01-15', 2024, 100,
            'en', 'Lançado', 'A synopsis', NULL, NULL
        );
        INSERT INTO dim_people VALUES ('p1', 'Director Example', 'Diretor');
        INSERT INTO fact_movies_performance VALUES (
            'm1', 10, 30, 20, 50, 150, 100, 5.5, 0, 0, 8, 5
        );
        INSERT INTO dim_reviews VALUES ('r1', 'm1', 2, 8);
        INSERT INTO movie_reviews VALUES
            (1, 'gold-review-1', 'm1', 'Reviewer One', 7, 'Comment one', '2025-01-01 00:00:00'),
            (2, 'gold-review-2', 'm1', 'Reviewer Two', 9, 'Comment two', '2025-01-02 00:00:00');
        INSERT INTO bridge_movie_company VALUES ('m1', 'c1');
        INSERT INTO bridge_movie_genre VALUES ('m1', 'g1');
        INSERT INTO bridge_movie_person VALUES ('m1', 'p1');
        """
    )
    connection.commit()
    connection.close()


@pytest.fixture
def operational_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    database_path = tmp_path / "operational.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND_DIRECTORY / "alembic.ini")), "head")
    yield database_url, database_path
    get_settings.cache_clear()


def test_gold_database_sync_updates_catalog_and_preserves_app_reviews(
    tmp_path: Path, operational_database: tuple[str, Path]
) -> None:
    database_url, operational_path = operational_database
    gold_path = tmp_path / "cinerocket.db"
    _create_gold_database(gold_path)

    first = seed_from_gold_database(database_url, gold_path, batch_size=1)
    assert first is not None
    assert first["dim_movies"] == 1
    assert first["movie_reviews"] == 2

    app = sqlite3.connect(operational_path)
    assert app.execute(
        "SELECT idioma_original FROM dim_movies WHERE sk_movie_id='m1'"
    ).fetchone()[0] == "en"
    app.execute(
        "INSERT INTO users (id, email, nome, password_hash, role) "
        "VALUES ('u1', 'user@example.test', 'App User', 'hash', 'user')"
    )
    app.execute(
        "INSERT INTO movie_reviews "
        "(sk_movie_review_id, sk_movie_id, user_id, nome, nota, comentario, visibilidade) "
        "VALUES ('app-review-1', 'm1', 'u1', 'App User', 4, 'Private app review', 'privada')"
    )
    app.execute(
        "UPDATE dim_reviews SET qtd_avaliacoes_usuarios=3, nota_media_usuarios=? "
        "WHERE sk_movie_id='m1'",
        (20 / 3,),
    )
    app.commit()
    app.close()

    source = sqlite3.connect(gold_path)
    source.execute(
        "UPDATE dim_movies SET titulo='Updated Gold Title', idioma_original='pt' "
        "WHERE sk_movie_id='m1'"
    )
    source.execute("UPDATE dim_reviews SET nota_media_usuarios=7.5 WHERE sk_movie_id='m1'")
    source.commit()
    source.close()

    second = seed_from_gold_database(database_url, gold_path, batch_size=1)
    assert second is not None
    app = sqlite3.connect(operational_path)
    assert app.execute("SELECT titulo FROM dim_movies WHERE sk_movie_id='m1'").fetchone()[0] == (
        "Updated Gold Title"
    )
    assert app.execute(
        "SELECT idioma_original FROM dim_movies WHERE sk_movie_id='m1'"
    ).fetchone()[0] == "pt"
    assert app.execute(
        "SELECT qtd_avaliacoes_usuarios, nota_media_usuarios FROM dim_reviews "
        "WHERE sk_movie_id='m1'"
    ).fetchone() == (3, pytest.approx((2 * 7.5 + 4) / 3))
    assert app.execute(
        "SELECT user_id, visibilidade, comentario FROM movie_reviews "
        "WHERE sk_movie_review_id='app-review-1'"
    ).fetchone() == ("u1", "privada", "Private app review")
    assert app.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    app.close()

    assert seed_from_gold_database(database_url, gold_path, batch_size=1) is None


def test_gold_database_sync_rejects_a_database_missing_gold_tables(
    tmp_path: Path, operational_database: tuple[str, Path]
) -> None:
    database_url, _ = operational_database
    incomplete_gold = tmp_path / "incomplete.db"
    sqlite3.connect(incomplete_gold).close()

    with pytest.raises(GoldDatabaseError, match="tabelas esperadas"):
        seed_from_gold_database(database_url, incomplete_gold)
