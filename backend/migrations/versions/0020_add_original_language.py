"""Add original language from the Gold movie dimension."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_add_original_language"
down_revision: str | Sequence[str] | None = "0019_track_gold_database_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dim_movies", sa.Column("idioma_original", sa.String(length=10)))


def downgrade() -> None:
    op.drop_column("dim_movies", "idioma_original")
