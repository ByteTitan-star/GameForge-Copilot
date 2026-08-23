"""M4 游戏生成三表

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("slug", sa.String(128), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requirement", sa.Text(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_games_owner_id", "games", ["owner_id"])
    op.create_index("ux_games_slug", "games", ["slug"], unique=True)

    op.create_table(
        "game_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "game_id", sa.Uuid(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("artifact_path", sa.String(512), nullable=False),
        sa.Column("design_doc", sa.JSON(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_game_versions_game_id", "game_versions", ["game_id"])

    op.create_table(
        "generation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "game_id", sa.Uuid(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "llm_config_id",
            sa.Uuid(),
            sa.ForeignKey("user_llm_config.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("phase", sa.String(16), nullable=True, server_default="plan"),
        sa.Column("checkpoint_ref", sa.String(255), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_generation_runs_game_id", "generation_runs", ["game_id"])
    op.create_index("ix_generation_runs_user_id", "generation_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_generation_runs_user_id", table_name="generation_runs")
    op.drop_index("ix_generation_runs_game_id", table_name="generation_runs")
    op.drop_table("generation_runs")

    op.drop_index("ix_game_versions_game_id", table_name="game_versions")
    op.drop_table("game_versions")

    op.drop_index("ux_games_slug", table_name="games")
    op.drop_index("ix_games_owner_id", table_name="games")
    op.drop_table("games")
