"""Add trigram indexes for substring searches in the catalog."""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_add_catalog_search_indexes"
down_revision: str | Sequence[str] | None = "0020_add_original_language"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEARCH_TABLES = (
    ("dim_movies", "dim_movies_search", "titulo"),
    ("dim_people", "dim_people_search", "nome_pessoa"),
    ("dim_companies", "dim_companies_search", "nome_produtora"),
)


def _create_triggers(table_name: str, search_name: str, column_name: str) -> None:
    op.execute(
        f"""CREATE TRIGGER {search_name}_ai AFTER INSERT ON {table_name} BEGIN
        INSERT INTO {search_name}(rowid, {column_name})
        VALUES (new.rowid, new.{column_name});
        END"""
    )
    op.execute(
        f"""CREATE TRIGGER {search_name}_ad AFTER DELETE ON {table_name} BEGIN
        INSERT INTO {search_name}({search_name}, rowid, {column_name})
        VALUES ('delete', old.rowid, old.{column_name});
        END"""
    )
    op.execute(
        f"""CREATE TRIGGER {search_name}_au AFTER UPDATE OF {column_name}
        ON {table_name} BEGIN
        INSERT INTO {search_name}({search_name}, rowid, {column_name})
        VALUES ('delete', old.rowid, old.{column_name});
        INSERT INTO {search_name}(rowid, {column_name})
        VALUES (new.rowid, new.{column_name});
        END"""
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise RuntimeError("Os índices trigramáticos do catálogo exigem SQLite com FTS5.")

    for table_name, search_name, column_name in SEARCH_TABLES:
        op.execute(
            f"""CREATE VIRTUAL TABLE {search_name} USING fts5(
                {column_name},
                content='{table_name}',
                content_rowid='rowid',
                tokenize='trigram',
                columnsize=0
            )"""
        )
        op.execute(f"INSERT INTO {search_name}({search_name}) VALUES ('rebuild')")
        _create_triggers(table_name, search_name, column_name)


def downgrade() -> None:
    for _table_name, search_name, _column_name in reversed(SEARCH_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {search_name}_au")
        op.execute(f"DROP TRIGGER IF EXISTS {search_name}_ad")
        op.execute(f"DROP TRIGGER IF EXISTS {search_name}_ai")
        op.execute(f"DROP TABLE IF EXISTS {search_name}")
