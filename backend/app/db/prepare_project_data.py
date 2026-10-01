"""Prepare project-local SQLite persistence before starting the API."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path


GOLD_TABLES = {
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


def _open_read_only(path: Path, *, immutable: bool = False) -> sqlite3.Connection:
    options = "mode=ro&immutable=1" if immutable else "mode=ro"
    return sqlite3.connect(f"{path.resolve().as_uri()}?{options}", uri=True)


def _validate_gold(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(
            f"Gold não encontrado em {path}. O clone precisa obter o arquivo "
            "cinerocket.db via Git LFS antes de executar o Docker Compose."
        )

    connection: sqlite3.Connection | None = None
    try:
        connection = _open_read_only(path)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = GOLD_TABLES - tables
        if missing:
            raise SystemExit(
                "O arquivo cinerocket.db não corresponde ao Gold esperado; "
                f"tabelas ausentes: {', '.join(sorted(missing))}. "
                "Confirme o checkout dos objetos Git LFS."
            )
        connection.execute("SELECT 1 FROM dim_movies LIMIT 1").fetchone()
    except sqlite3.DatabaseError as error:
        raise SystemExit(
            "O cinerocket.db não é um SQLite legível. Confirme que o Git LFS "
            "baixou o arquivo completo; não use o arquivo pointer do LFS."
        ) from error
    finally:
        if connection is not None:
            connection.close()


def _validate_gold_fingerprint(path: Path) -> None:
    manifest_value = os.environ.get("GOLD_DATABASE_FINGERPRINT_PATH")
    if not manifest_value:
        return
    manifest = Path(manifest_value)
    if not manifest.is_file():
        raise SystemExit(f"Manifesto SHA-256 do Gold não encontrado em {manifest}.")
    try:
        parts = manifest.read_text(encoding="ascii").split()
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            raise ValueError("formato inválido")
        expected_size = int(parts[1])
    except (OSError, UnicodeError, ValueError) as error:
        raise SystemExit(
            f"Manifesto SHA-256 inválido em {manifest}; esperado: SHA-256 e tamanho."
        ) from error
    if expected_size != path.stat().st_size:
        raise SystemExit(
            f"O tamanho de {path} não corresponde ao manifesto {manifest}; "
            "atualize o Gold e seu checksum em conjunto."
        )


def _validate_operational_database(path: Path) -> None:
    connection: sqlite3.Connection | None = None
    try:
        connection = _open_read_only(path)
        has_alembic_version = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'alembic_version'"
        ).fetchone()
        if not has_alembic_version:
            raise SystemExit(
                f"Existe um arquivo em {path}, mas ele não contém a tabela "
                "alembic_version. O arquivo foi preservado; verifique antes "
                "de remover ou substituir qualquer banco."
            )
    except sqlite3.DatabaseError as error:
        raise SystemExit(
            f"Não foi possível ler o banco operacional em {path}. "
            "O arquivo original foi preservado."
        ) from error
    finally:
        if connection is not None:
            connection.close()


def _restore_legacy_database(source: Path, target: Path) -> bool:
    if not source.is_file():
        return False

    wal_path = source.with_name(source.name + "-wal")
    if wal_path.is_file() and wal_path.stat().st_size > 0:
        raise SystemExit(
            "O banco operacional legado tem um arquivo WAL não vazio. Pare a "
            "aplicação que usa o volume antigo e faça um checkpoint antes da "
            "migração; nenhum arquivo do volume legado foi alterado."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection: sqlite3.Connection | None = None
    target_connection: sqlite3.Connection | None = None
    try:
        # Volumes antigos podem manter o header SQLite em modo WAL mesmo após
        # checkpoint. `immutable=1` permite ler sem criar -shm no mount :ro.
        source_connection = _open_read_only(source, immutable=True)
        target_connection = sqlite3.connect(target)
        source_connection.backup(target_connection)
        result = target_connection.execute("PRAGMA quick_check").fetchone()
        if result != ("ok",):
            raise sqlite3.DatabaseError(f"quick_check retornou {result!r}")
    except Exception:
        if target_connection is not None:
            target_connection.close()
            target_connection = None
        target.unlink(missing_ok=True)
        target.with_name(target.name + "-wal").unlink(missing_ok=True)
        target.with_name(target.name + "-shm").unlink(missing_ok=True)
        raise
    finally:
        if source_connection is not None:
            source_connection.close()
        if target_connection is not None:
            target_connection.close()

    return True


def prepare_project_data() -> None:
    data_directory = Path(
        os.environ.get("PROJECT_DATA_DIRECTORY", "/app/data")
    )
    legacy_directory = Path(
        os.environ.get("LEGACY_DATABASE_DIRECTORY", "/legacy")
    )
    gold_path = Path(
        os.environ.get("GOLD_DATABASE_PATH", "/workspace/cinerocket.db")
    )
    data_directory.mkdir(parents=True, exist_ok=True)
    _validate_gold(gold_path)
    _validate_gold_fingerprint(gold_path)

    operational_database = data_directory / "rocketlab.db"
    if operational_database.exists():
        _validate_operational_database(operational_database)
        print(f"Banco operacional do projeto preservado: {operational_database}")
        return

    legacy_database = legacy_directory / "rocketlab.db"
    if _restore_legacy_database(legacy_database, operational_database):
        print(
            "Banco operacional migrado do volume Docker antigo para "
            f"{operational_database}; o volume de origem foi mantido."
        )
        return

    print(
        "Nenhum banco operacional anterior foi encontrado; Alembic criará "
        f"{operational_database} na primeira inicialização."
    )


if __name__ == "__main__":
    prepare_project_data()
