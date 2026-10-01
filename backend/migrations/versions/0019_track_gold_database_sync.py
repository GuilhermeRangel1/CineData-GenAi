"""Track the Gold dataset version applied to the operational database."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_track_gold_database_sync"
down_revision: str | Sequence[str] | None = "0018_add_dislike_reaction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gold_database_sync",
        sa.Column("dataset_name", sa.String(length=80), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("dataset_name"),
    )


def downgrade() -> None:
    op.drop_table("gold_database_sync")
