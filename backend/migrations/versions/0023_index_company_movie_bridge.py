"""Index movie-company lookups used by the catalog filters."""

from collections.abc import Sequence

from alembic import op

revision: str = "0023_index_company_movie_bridge"
down_revision: str | Sequence[str] | None = "0022_cache_gold_fingerprint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_bridge_movie_company_sk_company_id",
        "bridge_movie_company",
        ["sk_company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bridge_movie_company_sk_company_id",
        table_name="bridge_movie_company",
    )
