"""0016: P1 Memory——user_preferences + games.session_summary_json。"""

import sqlalchemy as sa

from alembic import op

revision = "0016_memory_preferences"
down_revision = "0015_game_covers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "category", "key", name="uq_user_pref_user_cat_key"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])
    op.create_index(
        "ix_user_preferences_user_status", "user_preferences", ["user_id", "status"]
    )
    op.add_column(
        "games",
        sa.Column("session_summary_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("games", "session_summary_json")
    op.drop_index("ix_user_preferences_user_status", table_name="user_preferences")
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
