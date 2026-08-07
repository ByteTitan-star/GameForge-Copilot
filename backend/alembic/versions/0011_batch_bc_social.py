"""0011: entry_phase, profile, reactions, featured (Batch B/C)."""

import sqlalchemy as sa

from alembic import op

revision = "0011_batch_bc_social"
down_revision = "0010_oauth_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("entry_phase", sa.String(8), nullable=False, server_default="plan"),
    )
    op.add_column("users", sa.Column("handle", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("display_name", sa.String(64), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile_public", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_users_handle", "users", ["handle"], unique=True)
    op.add_column("games", sa.Column("featured_rank", sa.Integer(), nullable=True))
    op.create_index("ix_games_featured_rank", "games", ["featured_rank"])
    op.create_table(
        "game_reactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "game_id",
            sa.Uuid(),
            sa.ForeignKey("games.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "game_id", "type", name="uq_game_reaction"),
    )
    op.create_index("ix_game_reactions_game_id", "game_reactions", ["game_id"])
    op.create_index("ix_game_reactions_user_id", "game_reactions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_game_reactions_user_id", table_name="game_reactions")
    op.drop_index("ix_game_reactions_game_id", table_name="game_reactions")
    op.drop_table("game_reactions")
    op.drop_index("ix_games_featured_rank", table_name="games")
    op.drop_column("games", "featured_rank")
    op.drop_index("ix_users_handle", table_name="users")
    op.drop_column("users", "profile_public")
    op.drop_column("users", "display_name")
    op.drop_column("users", "handle")
    op.drop_column("generation_runs", "entry_phase")
