"""Prepare project-local SQLite persistence before starting the API."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from contextlib import closing
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

BOOTSTRAP_MARKER_SUFFIX = ".gold-bootstrap.json"
BASELINE_ALEMBIC_REVISION = "0001_initial_movie_schema"
# Este snapshot foi validado com as migrações 0002-0024. Um Gold diferente
# usa a importação tradicional até que seu schema seja validado novamente.
BOOTSTRAP_GOLD_SHA256 = "d4148542670284ef9e87d686fe7124f7a9c3ae5d1a62d19ad45ee685208b4eb7"
BOOTSTRAP_GOLD_SIZE = 722_337_792


def _bootstrap_marker_path(database: Path) -> Path:
    return database.with_name(database.name + BOOTSTRAP_MARKER_SUFFIX)


def _remove_sqlite_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        database.with_name(database.name + suffix).unlink(missing_ok=True)


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


def _source_identity(path: Path) -> tuple[str, int] | None:
    """Identifica o Gold pelo manifesto, quando ele está disponível."""

    manifest_value = os.environ.get("GOLD_DATABASE_FINGERPRINT_PATH")
    if not manifest_value:
        return None
    manifest = Path(manifest_value)
    parts = manifest.read_text(encoding="ascii").split()
    return parts[0].lower(), path.stat().st_size


def _rebuild_gold_reviews(connection: sqlite3.Connection) -> None:
    """Converte a única tabela Gold cuja estrutura difere do CineData."""

    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute("ALTER TABLE movie_reviews RENAME TO gold_movie_reviews")
    connection.execute(
        """
        CREATE TABLE movie_reviews (
            sk_movie_review_id VARCHAR(64) NOT NULL PRIMARY KEY,
            sk_movie_id VARCHAR(64) NOT NULL REFERENCES dim_movies(sk_movie_id) ON DELETE CASCADE,
            nome VARCHAR(120) NOT NULL,
            nota DOUBLE NOT NULL,
            comentario VARCHAR(4000) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            CONSTRAINT ck_movie_reviews_nota_range CHECK (nota >= 0 AND nota <= 10)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO movie_reviews (
            sk_movie_review_id, sk_movie_id, nome, nota, comentario, created_at
        )
        SELECT sk_movie_review_id, sk_movie_id, name, rating, text, created_at
        FROM gold_movie_reviews
        """
    )
    connection.execute("DROP TABLE gold_movie_reviews")
    connection.execute(
        "CREATE INDEX ix_movie_reviews_sk_movie_id ON movie_reviews (sk_movie_id)"
    )
    connection.execute("PRAGMA foreign_keys=ON")


def _bootstrap_from_gold(
    source: Path, target: Path, expected_digest: str, expected_size: int
) -> float:
    """Copia o snapshot Gold em bloco e o deixa pronto para as migrações locais."""

    started = time.perf_counter()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".bootstrap")
    marker = _bootstrap_marker_path(target)
    temporary_marker = marker.with_name(marker.name + ".bootstrap")
    temporary.unlink(missing_ok=True)
    _remove_sqlite_sidecars(temporary)
    temporary_marker.unlink(missing_ok=True)
    try:
        digest = hashlib.sha256()
        copied = 0
        with source.open("rb") as origin, temporary.open("xb") as destination:
            while block := origin.read(8 * 1024 * 1024):
                destination.write(block)
                digest.update(block)
                copied += len(block)
        if copied != expected_size or digest.hexdigest() != expected_digest:
            raise ValueError("O conteúdo do Gold não corresponde ao manifesto SHA-256.")
        with closing(sqlite3.connect(temporary)) as connection:
            with connection:
                _rebuild_gold_reviews(connection)
                connection.execute("DELETE FROM alembic_version")
                connection.execute(
                    "INSERT INTO alembic_version (version_num) VALUES (?)",
                    (BASELINE_ALEMBIC_REVISION,),
                )
                result = connection.execute("PRAGMA quick_check('movie_reviews')").fetchone()
                if result != ("ok",):
                    raise sqlite3.DatabaseError(f"quick_check retornou {result!r}")
                violation = connection.execute(
                    "PRAGMA foreign_key_check('movie_reviews')"
                ).fetchone()
                if violation is not None:
                    raise sqlite3.IntegrityError(
                        f"movie_reviews contém uma referência inválida: {violation!r}"
                    )
            checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is None or checkpoint[0] != 0:
                raise sqlite3.DatabaseError("Não foi possível consolidar o WAL temporário.")
            mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
            if mode is None or mode[0].lower() != "delete":
                raise sqlite3.DatabaseError("Não foi possível finalizar o SQLite temporário.")
        for suffix in ("-wal", "-shm"):
            sidecar = temporary.with_name(temporary.name + suffix)
            if sidecar.is_file() and sidecar.stat().st_size:
                raise sqlite3.DatabaseError(f"Arquivo SQLite temporário não consolidado: {sidecar}")
        _remove_sqlite_sidecars(temporary)
        temporary_marker.write_text(
            f"{expected_digest} {expected_size}\n", encoding="ascii"
        )
        os.replace(temporary, target)
        os.replace(temporary_marker, marker)
        return time.perf_counter() - started
    except Exception:
        temporary.unlink(missing_ok=True)
        _remove_sqlite_sidecars(temporary)
        temporary_marker.unlink(missing_ok=True)
        raise


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

    identity = _source_identity(gold_path)
    if identity != (BOOTSTRAP_GOLD_SHA256, BOOTSTRAP_GOLD_SIZE):
        print(
            "Snapshot Gold diferente do validado para cópia direta; "
            "Alembic e a sincronização tradicional prepararão o banco.",
            flush=True,
        )
        return

    print("Preparando cópia local do Gold para a primeira inicialização...", flush=True)
    try:
        elapsed = _bootstrap_from_gold(gold_path, operational_database, *identity)
    except (OSError, sqlite3.Error, ValueError) as error:
        operational_database.unlink(missing_ok=True)
        _bootstrap_marker_path(operational_database).unlink(missing_ok=True)
        raise SystemExit(
            "Não foi possível preparar o banco operacional a partir do Gold; "
            "nenhum banco parcial foi mantido."
        ) from error
    print(
        "Cópia do Gold preparada em "
        f"{elapsed:.1f}s; as migrações locais serão aplicadas pelo backend.",
        flush=True,
    )


if __name__ == "__main__":
    prepare_project_data()
