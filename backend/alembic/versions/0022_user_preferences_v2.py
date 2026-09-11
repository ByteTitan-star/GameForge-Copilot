"""0022: user_preferences_v2 for ADR-16 canonical preference memory."""

import sqlalchemy as sa

from alembic import op

revision = "0022_user_preferences_v2"
down_revision = "0021_knowledge_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("preference_key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("value_type", sa.String(length=8), nullable=False, server_default="enum"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="explicit"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
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
        sa.UniqueConstraint("user_id", "preference_key", name="uq_user_pref_v2_user_key"),
    )
    op.create_index(
        "ix_user_pref_v2_user_status_lru",
        "user_preferences_v2",
        ["user_id", "status", "last_used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_pref_v2_user_status_lru", table_name="user_preferences_v2")
    op.drop_table("user_preferences_v2")
