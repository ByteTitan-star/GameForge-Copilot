"""Add published_at and play_count for public discovery (B2)."""

import sqlalchemy as sa

from alembic import op

revision = "0009_public_games"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("play_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("games", "play_count")
    op.drop_column("games", "published_at")
