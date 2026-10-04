from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.db.prepare_project_data import (
    BASELINE_ALEMBIC_REVISION,
    _bootstrap_from_gold,
    _bootstrap_marker_path,
)


def _gold_fixture(path: Path) -> tuple[str, int]:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);
            INSERT INTO alembic_version VALUES ('0001_initial_schema');
            CREATE TABLE dim_movies (sk_movie_id TEXT PRIMARY KEY);
            INSERT INTO dim_movies VALUES ('movie-1');
            CREATE TABLE movie_reviews (
                id INTEGER PRIMARY KEY,
                sk_movie_review_id TEXT NOT NULL,
                sk_movie_id TEXT NOT NULL REFERENCES dim_movies(sk_movie_id),
                name TEXT NOT NULL,
                rating REAL NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO movie_reviews VALUES
                (1, 'review-1', 'movie-1', 'Pessoa', 8, 'Comentário', '2026-01-01');
            """
        )
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size


def test_gold_bootstrap_checkpoints_wal_before_publishing_database(tmp_path: Path) -> None:
    source = tmp_path / "gold.db"
    target = tmp_path / "operational.db"
    digest, size = _gold_fixture(source)

    _bootstrap_from_gold(source, target, digest, size)

    assert _bootstrap_marker_path(target).read_text(encoding="ascii") == f"{digest} {size}\n"
    assert not list(tmp_path.glob("operational.db.bootstrap*"))
    with sqlite3.connect(target) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            BASELINE_ALEMBIC_REVISION,
        )
        assert connection.execute(
            "SELECT sk_movie_review_id, nome, nota, comentario FROM movie_reviews"
        ).fetchone() == ("review-1", "Pessoa", 8, "Comentário")
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None


def test_gold_bootstrap_rejects_wrong_checksum_without_partial_database(tmp_path: Path) -> None:
    source = tmp_path / "gold.db"
    target = tmp_path / "operational.db"
    _digest, size = _gold_fixture(source)

    with pytest.raises(ValueError, match="SHA-256"):
        _bootstrap_from_gold(source, target, "0" * 64, size)

    assert not target.exists()
    assert not _bootstrap_marker_path(target).exists()
    assert not list(tmp_path.glob("operational.db.bootstrap*"))
