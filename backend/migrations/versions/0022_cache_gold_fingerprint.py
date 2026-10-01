"""Record the Gold LFS digest to skip full-file hashing on startup."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_cache_gold_fingerprint"
down_revision: str | Sequence[str] | None = "0021_add_catalog_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gold_database_sync",
        sa.Column("source_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "gold_database_sync",
        sa.Column("source_digest", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gold_database_sync", "source_digest")
    op.drop_column("gold_database_sync", "source_size_bytes")
