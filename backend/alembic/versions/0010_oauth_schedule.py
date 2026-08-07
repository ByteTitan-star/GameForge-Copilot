"""0010: OAuth 账号 + 游戏定时上下架字段（B7/B8）。"""

import sqlalchemy as sa

from alembic import op

revision = "0010_oauth_schedule"
down_revision = "0009_public_games"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_sub", name="uq_oauth_provider_sub"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])
    op.add_column(
        "games",
        sa.Column("scheduled_take_down_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("games", "scheduled_publish_at")
    op.drop_column("games", "scheduled_take_down_at")
    op.drop_index("ix_oauth_accounts_user_id", "oauth_accounts")
    op.drop_table("oauth_accounts")
