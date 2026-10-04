"""Sincroniza o banco Gold fornecido para o SQLite operacional do CineData."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import sys
from collections.abc import Iterator, Sequence
from contextlib import closing
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, bindparam, create_engine, event, inspect, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.schema import Table

from app.communities import models as community_models  # noqa: F401  Registra as tabelas sociais.
from app.conversations import (
    models as conversation_models,  # noqa: F401  Registra o histórico privado.
)
from app.db.base import Base, GoldDatabaseSync
from app.movies import models as movie_models  # noqa: F401  Registra as tabelas do catálogo.
from app.users import models as user_models  # noqa: F401  Registra as tabelas de contas.

DEFAULT_BATCH_SIZE = 10_000
DEFAULT_GOLD_DATABASE = Path(__file__).resolve().parents[3] / "data" / "cinerocket.db"
GOLD_IMPORT_VERSION = "2"
BOOTSTRAP_MARKER_SUFFIX = ".gold-bootstrap.json"

# A revisão e855f43 acrescentou apenas índices ao arquivo Gold. O checksum
# físico mudou, mas as dez tabelas importadas permaneceram iguais. Reconhecer
# essa transição evita reimportar todo o catálogo em cada inicialização.
INDEX_ONLY_GOLD_REVISIONS = {
    (
        "410f5beef6ab9fb34b9044d5dd191f56f3f0dc30a56e6432386ecef0d977b012",
        581120000,
        "d4148542670284ef9e87d686fe7124f7a9c3ae5d1a62d19ad45ee685208b4eb7",
        722337792,
    ),
}


def _synchronous_url(database_url: str) -> str:
    """Converte a URL async usada pela aplicação para a conexão síncrona da CLI."""

    return database_url.replace("+aiosqlite", "")


def _bootstrap_marker_path(database: str | None) -> Path | None:
    if not database or database == ":memory:":
        return None
    target = Path(database).expanduser().resolve()
    return target.with_name(target.name + BOOTSTRAP_MARKER_SUFFIX)


def _consume_bootstrap_marker(
    database: str | None, source_digest: str, source_size: int
) -> bool:
    """Confirma que o banco novo é uma cópia direta do Gold atual."""

    marker = _bootstrap_marker_path(database)
    if marker is None or not marker.is_file():
        return False
    try:
        parts = marker.read_text(encoding="ascii").split()
        return (
            len(parts) == 2
            and int(parts[1]) == source_size
            and parts[0].lower() == source_digest
        )
    except (OSError, UnicodeError, ValueError):
        return False


def _remove_bootstrap_marker(database: str | None) -> None:
    marker = _bootstrap_marker_path(database)
    if marker is not None:
        marker.unlink(missing_ok=True)

GOLD_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "dim_companies": ("sk_company_id", "nome_produtora"),
    "dim_genres": ("sk_genre_id", "nome_genero"),
    "dim_movies": (
        "sk_movie_id",
        "id_filme",
        "titulo",
        "data_lancamento",
        "ano_lancamento",
        "duracao_minutos",
        "idioma_original",
        "status_filme",
        "sinopse",
        "url_poster",
        "url_backdrop",
    ),
    "dim_people": ("sk_person_id", "nome_pessoa", "tipo_pessoa"),
    "fact_movies_performance": (
        "sk_movie_id",
        "orcamento_usd",
        "receita_usd",
        "lucro_usd",
        "orcamento_brl",
        "receita_brl",
        "lucro_brl",
        "popularidade",
        "nota_tmdb",
        "qtd_tmdb",
        "nota_imdb",
        "qtd_imdb",
    ),
    "dim_reviews": (
        "sk_review_id",
        "sk_movie_id",
        "qtd_avaliacoes_usuarios",
        "nota_media_usuarios",
    ),
    "movie_reviews": (
        "sk_movie_review_id",
        "sk_movie_id",
        "nome",
        "nota",
        "comentario",
        "created_at",
    ),
    "bridge_movie_company": ("sk_movie_id", "sk_company_id"),
    "bridge_movie_genre": ("sk_movie_id", "sk_genre_id"),
    "bridge_movie_person": ("sk_movie_id", "sk_person_id"),
}

UPSERT_COLUMNS: dict[str, tuple[str, ...]] = {
    "dim_companies": ("nome_produtora",),
    "dim_genres": ("nome_genero",),
    "dim_movies": (
        "id_filme",
        "titulo",
        "data_lancamento",
        "ano_lancamento",
        "duracao_minutos",
        "idioma_original",
        "status_filme",
        "sinopse",
        "url_poster",
        "url_backdrop",
    ),
    "dim_people": ("nome_pessoa", "tipo_pessoa"),
    "fact_movies_performance": GOLD_TABLE_COLUMNS["fact_movies_performance"][1:],
    "dim_reviews": (
        "sk_review_id",
        "qtd_avaliacoes_usuarios",
        "nota_media_usuarios",
    ),
    "movie_reviews": ("sk_movie_id", "nome", "nota", "comentario", "created_at"),
}

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "dim_companies": ("sk_company_id",),
    "dim_genres": ("sk_genre_id",),
    "dim_movies": ("sk_movie_id",),
    "dim_people": ("sk_person_id",),
    "fact_movies_performance": ("sk_movie_id",),
    "dim_reviews": ("sk_movie_id",),
    "movie_reviews": ("sk_movie_review_id",),
    "bridge_movie_company": ("sk_movie_id", "sk_company_id"),
    "bridge_movie_genre": ("sk_movie_id", "sk_genre_id"),
    "bridge_movie_person": ("sk_movie_id", "sk_person_id"),
}

SOURCE_QUERIES = {
    **{
        name: f'SELECT {", ".join(columns)} FROM "{name}"'
        for name, columns in GOLD_TABLE_COLUMNS.items()
        if name != "movie_reviews"
    },
    "movie_reviews": (
        "SELECT sk_movie_review_id, sk_movie_id, name AS nome, rating AS nota, "
        "text AS comentario, COALESCE(created_at, CURRENT_TIMESTAMP) AS created_at "
        "FROM movie_reviews"
    ),
}


class GoldDatabaseError(ValueError):
    """Erro controlado ao validar ou importar a base Gold."""


def _configure_engine(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: object) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-65536")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def _gold_fingerprint(path: Path) -> tuple[str, str, int, bool]:
    """Uses the tracked LFS checksum so normal startups do not reread 581 MB."""
    configured_gold = Path(
        os.environ.get("GOLD_DATABASE_PATH", DEFAULT_GOLD_DATABASE)
    ).expanduser().resolve()
    configured_manifest = os.environ.get("GOLD_DATABASE_FINGERPRINT_PATH")
    manifest_path = (
        Path(configured_manifest)
        if configured_manifest and configured_gold == path.resolve()
        else Path(f"{path}.sha256")
    )
    source_size = path.stat().st_size
    manifest_digest: str | None = None
    if manifest_path.is_file():
        parts = manifest_path.read_text(encoding="ascii").split()
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            raise GoldDatabaseError(
                f"Manifesto de fingerprint inválido em {manifest_path}; esperado: SHA256 e tamanho."
            )
        try:
            expected_size = int(parts[1])
        except ValueError as error:
            raise GoldDatabaseError(
                f"Tamanho inválido no manifesto de fingerprint {manifest_path}."
            ) from error
        if expected_size != source_size:
            raise GoldDatabaseError(
                f"O tamanho de {path} não corresponde ao manifesto {manifest_path}; "
                "atualize o Gold e seu checksum em conjunto."
            )
        manifest_digest = parts[0].lower()

    if manifest_digest is None:
        # Bases customizadas sem manifesto continuam usando hash integral.
        source_hash = hashlib.sha256()
        with path.open("rb") as source:
            while block := source.read(8 * 1024 * 1024):
                source_hash.update(block)
        source_digest = source_hash.hexdigest()
    else:
        source_digest = manifest_digest

    digest = hashlib.sha256()
    digest.update(f"gold-import-version:{GOLD_IMPORT_VERSION}\0".encode())
    digest.update(bytes.fromhex(source_digest))
    return digest.hexdigest(), source_digest, source_size, manifest_digest is not None


def _legacy_gold_fingerprint(path: Path) -> str:
    """Recognizes the pre-manifest fingerprint once when upgrading an existing DB."""
    digest = hashlib.sha256()
    digest.update(f"gold-import-version:{GOLD_IMPORT_VERSION}\0".encode())
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _fingerprint_from_digest(source_digest: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"gold-import-version:{GOLD_IMPORT_VERSION}\0".encode())
    digest.update(bytes.fromhex(source_digest))
    return digest.hexdigest()


def _create_pre_sync_backup(engine: Engine) -> Path | None:
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    target_path = Path(database).expanduser().resolve()
    if not target_path.is_file():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = target_path.with_name(f"{target_path.stem}.pre-gold-{stamp}{target_path.suffix}")
    suffix = 1
    while backup_path.exists():
        backup_path = target_path.with_name(
            f"{target_path.stem}.pre-gold-{stamp}-{suffix}{target_path.suffix}"
        )
        suffix += 1
    try:
        with (
            closing(sqlite3.connect(f"{target_path.as_uri()}?mode=ro", uri=True)) as original,
            closing(sqlite3.connect(backup_path)) as backup,
        ):
            original.backup(backup)
    except sqlite3.Error as error:
        raise GoldDatabaseError(
            "Não foi possível criar o backup do banco operacional antes da sincronização."
        ) from error
    return backup_path


def _has_application_data(connection: Any, tables: dict[str, Table]) -> bool:
    excluded = {"alembic_version", "gold_database_sync"}
    existing_tables = set(inspect(connection).get_table_names())
    for table_name, table in tables.items():
        if table_name in excluded or table_name not in existing_tables:
            continue
        if connection.execute(select(table.c[next(iter(table.c.keys()))]).limit(1)).first():
            return True
    return False


def _readonly_sqlite(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection
    except sqlite3.Error as error:
        raise GoldDatabaseError("Não foi possível abrir a base Gold em leitura.") from error


def _validate_source(source: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing = sorted(set(GOLD_TABLE_COLUMNS) - tables)
    if missing:
        raise GoldDatabaseError(
            "A base Gold não contém todas as tabelas esperadas: " + ", ".join(missing) + "."
        )

    for table, expected_columns in GOLD_TABLE_COLUMNS.items():
        actual_columns = {
            row[1] for row in source.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        if table == "movie_reviews":
            required_columns = {
                "sk_movie_review_id",
                "sk_movie_id",
                "name",
                "rating",
                "text",
                "created_at",
            }
        else:
            required_columns = set(expected_columns)
        missing_columns = sorted(required_columns - actual_columns)
        if missing_columns:
            raise GoldDatabaseError(
                f"A tabela {table} não contém as colunas esperadas: "
                + ", ".join(missing_columns)
                + "."
            )


def _as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _prepare_row(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    if table_name == "dim_movies":
        item["data_lancamento"] = _as_date(item["data_lancamento"])
        duration = item["duracao_minutos"]
        if duration is not None and duration <= 0:
            item["duracao_minutos"] = None
    elif table_name == "fact_movies_performance":
        for column in (
            "orcamento_usd",
            "receita_usd",
            "lucro_usd",
            "orcamento_brl",
            "receita_brl",
            "lucro_brl",
        ):
            if item[column] is not None:
                item[column] = Decimal(str(item[column]))
        for column in ("nota_tmdb", "nota_imdb"):
            votes_column = "qtd_tmdb" if column == "nota_tmdb" else "qtd_imdb"
            if item[votes_column] == 0:
                item[column] = None
    elif table_name == "dim_reviews":
        item["qtd_avaliacoes_usuarios"] = int(item["qtd_avaliacoes_usuarios"])
        if item["qtd_avaliacoes_usuarios"] < 0:
            raise GoldDatabaseError("A base Gold contém uma contagem de avaliações negativa.")
        if item["nota_media_usuarios"] is not None:
            item["nota_media_usuarios"] = float(item["nota_media_usuarios"])
            if not 0 <= item["nota_media_usuarios"] <= 10:
                raise GoldDatabaseError("A base Gold contém uma média fora da escala de 0 a 10.")
    elif table_name == "movie_reviews":
        item["nota"] = float(item["nota"])
        if not 0 <= item["nota"] <= 10:
            raise GoldDatabaseError("A base Gold contém uma avaliação fora da escala de 0 a 10.")
        item["created_at"] = _as_datetime(item["created_at"])
    return item


def _batches(
    cursor: sqlite3.Cursor, table_name: str, batch_size: int
) -> Iterator[list[dict[str, Any]]]:
    while rows := cursor.fetchmany(batch_size):
        yield [_prepare_row(table_name, row) for row in rows]


def _apply_table(
    connection: Any,
    source: sqlite3.Connection,
    table_name: str,
    table: Table,
    batch_size: int,
) -> int:
    insert = sqlite_insert(table)
    keys = PRIMARY_KEYS[table_name]
    updates = UPSERT_COLUMNS.get(table_name, ())
    if updates:
        statement = insert.on_conflict_do_update(
            index_elements=[table.c[key] for key in keys],
            set_={column: getattr(insert.excluded, column) for column in updates},
        )
    else:
        statement = insert.on_conflict_do_nothing(
            index_elements=[table.c[key] for key in keys]
        )

    cursor = source.execute(SOURCE_QUERIES[table_name])
    processed = 0
    for batch in _batches(cursor, table_name, batch_size):
        connection.execute(statement, batch)
        processed += len(batch)
    return processed


def _merge_user_review_summaries(
    connection: Any,
    review_summary_table: Table,
    source_summaries: dict[str, tuple[int, float | None]],
) -> None:
    if not source_summaries:
        return
    user_reviews = connection.execute(
        text(
            "SELECT sk_movie_id, COUNT(*) AS review_count, SUM(nota) AS rating_sum "
            "FROM movie_reviews WHERE user_id IS NOT NULL GROUP BY sk_movie_id"
        )
    )
    statement = (
        update(review_summary_table)
        .where(review_summary_table.c.sk_movie_id == bindparam("movie_key"))
        .values(
            qtd_avaliacoes_usuarios=bindparam("review_count"),
            nota_media_usuarios=bindparam("average_rating"),
        )
    )
    updates: list[dict[str, Any]] = []
    for row in user_reviews:
        baseline = source_summaries.get(row.sk_movie_id)
        if baseline is None:
            continue
        baseline_count, baseline_average = baseline
        total_count = baseline_count + row.review_count
        weighted_total = (baseline_average or 0.0) * baseline_count + row.rating_sum
        updates.append(
            {
                "movie_key": row.sk_movie_id,
                "review_count": total_count,
                "average_rating": weighted_total / total_count,
            }
        )
    if updates:
        connection.execute(statement, updates)


def seed_from_gold_database(
    database_url: str,
    gold_database: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force: bool = False,
) -> dict[str, int] | None:
    """Idempotently synchronizes Gold tables while retaining app-owned records."""

    if batch_size < 1:
        raise ValueError("batch_size deve ser maior que zero.")
    source_path = gold_database.expanduser().resolve()
    if not source_path.is_file():
        raise GoldDatabaseError(
            "Banco Gold não encontrado. Obtenha o arquivo cinerocket.db conforme o README "
            "e coloque-o em data/cinerocket.db, configure GOLD_DATABASE_PATH ou informe "
            f"--gold-database. Caminho procurado: {source_path}."
        )

    engine = create_engine(_synchronous_url(database_url))
    if engine.dialect.name != "sqlite":
        engine.dispose()
        raise GoldDatabaseError("A sincronização da base Gold requer um banco SQLite operacional.")
    target_database = engine.url.database
    if target_database and Path(target_database).expanduser().resolve() == source_path:
        engine.dispose()
        raise GoldDatabaseError(
            "A base Gold deve ser somente leitura; configure um arquivo operacional separado."
        )
    _configure_engine(engine)

    try:
        source = _readonly_sqlite(source_path)
    except GoldDatabaseError:
        engine.dispose()
        raise
    try:
        _validate_source(source)
        _asserted_tables = set(inspect(engine).get_table_names())
        missing_target = sorted(set(Base.metadata.tables) - _asserted_tables)
        if missing_target or "alembic_version" not in _asserted_tables:
            missing = ", ".join(missing_target) or "alembic_version"
            raise GoldDatabaseError(
                "O banco operacional precisa receber as migrações antes da sincronização; "
                f"faltam: {missing}."
            )

        fingerprint, source_digest, source_size, has_manifest = _gold_fingerprint(source_path)
        tables = Base.metadata.tables
        bootstrapped_from_current_gold = _consume_bootstrap_marker(
            target_database, source_digest, source_size
        )
        backup_path = None
        with engine.connect() as connection:
            previous_sync = connection.execute(
                select(
                    GoldDatabaseSync.fingerprint,
                    GoldDatabaseSync.source_digest,
                    GoldDatabaseSync.source_size_bytes,
                ).where(
                    GoldDatabaseSync.dataset_name == "cinerocket"
                )
            ).one_or_none()
            previous = previous_sync.fingerprint if previous_sync else None
            if (
                previous_sync is not None
                and previous_sync.source_digest is None
                and previous_sync.source_size_bytes is None
                and has_manifest
                and _legacy_gold_fingerprint(source_path) == previous
            ):
                # Atualiza somente o formato do fingerprint na migração da lógica;
                # não cria um backup/reimport desnecessário de 679 MB.
                previous = fingerprint
            elif (
                previous_sync is not None
                and previous_sync.source_digest is not None
                and (
                    previous_sync.source_digest,
                    previous_sync.source_size_bytes,
                    source_digest,
                    source_size,
                ) in INDEX_ONLY_GOLD_REVISIONS
                and previous == _fingerprint_from_digest(previous_sync.source_digest)
            ):
                previous = fingerprint
            has_application_data = (
                not bootstrapped_from_current_gold
                and (force or previous != fingerprint)
                and _has_application_data(connection, tables)
            )
        if has_application_data:
            backup_path = _create_pre_sync_backup(engine)
        if (previous == fingerprint or bootstrapped_from_current_gold) and not force:
            with engine.begin() as connection:
                connection.execute(
                    sqlite_insert(GoldDatabaseSync)
                    .values(
                        dataset_name="cinerocket",
                        fingerprint=fingerprint,
                        source_size_bytes=source_size,
                        source_digest=source_digest,
                    )
                    .on_conflict_do_update(
                        index_elements=[GoldDatabaseSync.dataset_name],
                        set_={
                            "fingerprint": fingerprint,
                            "imported_at": text("CURRENT_TIMESTAMP"),
                            "source_size_bytes": source_size,
                            "source_digest": source_digest,
                        },
                    )
                )
            if bootstrapped_from_current_gold:
                _remove_bootstrap_marker(target_database)
                print(
                    "Base Gold adotada por cópia direta; "
                    "importação linha a linha ignorada.",
                    flush=True,
                )
            return None
        if backup_path is not None:
            print(f"Backup preventivo criado: {backup_path}", flush=True)

        source_summaries = {
            row["sk_movie_id"]: (
                int(row["qtd_avaliacoes_usuarios"]),
                float(row["nota_media_usuarios"])
                if row["nota_media_usuarios"] is not None
                else None,
            )
            for row in source.execute(
                "SELECT sk_movie_id, qtd_avaliacoes_usuarios, nota_media_usuarios "
                "FROM dim_reviews"
            )
        }
        processed: dict[str, int] = {}
        with engine.begin() as connection:
            for table_name in (
                "dim_companies",
                "dim_genres",
                "dim_movies",
                "dim_people",
                "fact_movies_performance",
                "dim_reviews",
                "movie_reviews",
                "bridge_movie_company",
                "bridge_movie_genre",
                "bridge_movie_person",
            ):
                processed[table_name] = _apply_table(
                    connection,
                    source,
                    table_name,
                    tables[table_name],
                    batch_size,
                )
            _merge_user_review_summaries(
                connection, tables["dim_reviews"], source_summaries
            )
            connection.execute(
                sqlite_insert(GoldDatabaseSync)
                .values(
                    dataset_name="cinerocket",
                    fingerprint=fingerprint,
                    source_size_bytes=source_size,
                    source_digest=source_digest,
                )
                .on_conflict_do_update(
                    index_elements=[GoldDatabaseSync.dataset_name],
                    set_={
                        "fingerprint": fingerprint,
                        "imported_at": text("CURRENT_TIMESTAMP"),
                        "source_size_bytes": source_size,
                        "source_digest": source_digest,
                    },
                )
            )
        return processed
    except sqlite3.Error as error:
        raise GoldDatabaseError(
            "A leitura da base Gold falhou; a sincronização foi cancelada."
        ) from error
    except SQLAlchemyError as error:
        raise GoldDatabaseError(
            "A importação Gold falhou por incompatibilidade do schema ou dos dados; "
            "a transação foi revertida."
        ) from error
    finally:
        source.close()
        engine.dispose()


def _parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza o banco Gold CineData no banco operacional da aplicação."
    )
    parser.add_argument(
        "--database-url", required=True, help="URL do banco operacional migrado."
    )
    parser.add_argument(
        "--gold-database",
        type=Path,
        default=Path(os.environ.get("GOLD_DATABASE_PATH", DEFAULT_GOLD_DATABASE)),
        help=(
            "Caminho para cinerocket.db (padrão: GOLD_DATABASE_PATH ou "
            f"{DEFAULT_GOLD_DATABASE})."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Repete a sincronização mesmo sem alterações na base Gold.",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_arguments(arguments)
    try:
        summary = seed_from_gold_database(
            args.database_url,
            args.gold_database,
            batch_size=args.batch_size,
            force=args.force,
        )
    except ValueError as error:
        print(f"Sincronização não realizada: {error}", file=sys.stderr)
        return 1

    if summary is None:
        print("Base Gold sem alterações; banco operacional já está sincronizado.")
        return 0
    print("Banco operacional sincronizado a partir do Gold:")
    for table_name, count in summary.items():
        print(f"- {table_name}: {count:,} registros lidos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
