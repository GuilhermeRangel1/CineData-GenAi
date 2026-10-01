"""Acesso controlado e somente leitura à base Gold SQLite."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.errors import GoldInvalidError, GoldUnavailableError

EXPECTED_TABLES = frozenset(
    {
        "dim_movies",
        "fact_movies_performance",
        "dim_genres",
        "dim_people",
        "dim_companies",
        "dim_reviews",
        "movie_reviews",
        "bridge_movie_genre",
        "bridge_movie_person",
        "bridge_movie_company",
    }
)


@dataclass(frozen=True)
class GoldReadiness:
    """Informações mínimas obtidas durante a validação do Gold."""

    path: Path
    tables: frozenset[str]


class GoldDatabase:
    """Abre o arquivo Gold em URI SQLite `mode=ro` e valida sua estrutura."""

    def __init__(self, path: Path, timeout_seconds: float = 5.0) -> None:
        self.path = path.expanduser().resolve()
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Fornece uma conexão read-only e a fecha ao final do uso."""

        self._validate_file()
        uri = f"file:{self.path.as_posix()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=self.timeout_seconds)
        except sqlite3.Error as exc:
            raise GoldUnavailableError("A base Gold não está acessível.") from exc

        try:
            yield connection
        finally:
            connection.close()

    def check_readiness(self) -> GoldReadiness:
        """Valida integridade SQLite e presença das tabelas Gold esperadas."""

        with self.connect() as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise GoldInvalidError("A base Gold falhou na verificação de integridade.")

            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            tables = frozenset(row[0] for row in rows)

        missing = EXPECTED_TABLES - tables
        if missing:
            raise GoldInvalidError("A base Gold não contém todas as tabelas esperadas.")

        return GoldReadiness(path=self.path, tables=tables)

    def _validate_file(self) -> None:
        if not self.path.is_file():
            raise GoldUnavailableError("A base Gold não está disponível.")

        try:
            header = self.path.read_bytes()[:64]
        except OSError as exc:
            raise GoldUnavailableError("A base Gold não está acessível.") from exc

        if header.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise GoldUnavailableError("O objeto Git LFS da base Gold não foi baixado.")
