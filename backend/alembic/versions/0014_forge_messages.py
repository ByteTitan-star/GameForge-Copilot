"""0014: 持久化 Forge 用户可见对话。"""

import sqlalchemy as sa

from alembic import op

revision = "0014_forge_messages"
down_revision = "0013_forge_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forge_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_forge_message_dedupe_key"),
    )
    op.create_index("ix_forge_messages_game_id", "forge_messages", ["game_id"])
    op.create_index("ix_forge_messages_run_id", "forge_messages", ["run_id"])
    op.create_index("ix_forge_messages_user_id", "forge_messages", ["user_id"])
    op.create_index("ix_forge_messages_created_at", "forge_messages", ["created_at"])
    op.create_index("ix_forge_messages_game_created", "forge_messages", ["game_id", "created_at"])
    op.get_bind().exec_driver_sql(
        """
            INSERT INTO forge_messages (
                id, game_id, run_id, user_id, role, kind, content,
                metadata_json, dedupe_key, created_at
            )
            SELECT
                id, game_id, id, user_id, 'user', 'requirement', requirement,
                CAST('{}' AS JSON), CAST(id AS TEXT) || ':requirement', started_at
            FROM generation_runs
            """
    )


def downgrade() -> None:
    op.drop_index("ix_forge_messages_game_created", table_name="forge_messages")
    op.drop_index("ix_forge_messages_created_at", table_name="forge_messages")
    op.drop_index("ix_forge_messages_user_id", table_name="forge_messages")
    op.drop_index("ix_forge_messages_run_id", table_name="forge_messages")
    op.drop_index("ix_forge_messages_game_id", table_name="forge_messages")
    op.drop_table("forge_messages")
