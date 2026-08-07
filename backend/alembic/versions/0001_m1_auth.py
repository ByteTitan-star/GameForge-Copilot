"""M1 认证三表

Revision ID: 0001
Revises:
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str) -> sa.Column:
    """created_at / updated_at 公共列。"""
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    _create_token_table("email_verification")
    _create_token_table("password_reset_tokens")


def _create_token_table(name: str) -> None:
    """email_verification / password_reset_tokens 同构。"""
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index(f"ix_{name}_user_id", name, ["user_id"])
    op.create_index(f"ix_{name}_token_hash", name, ["token_hash"], unique=True)


def downgrade() -> None:
    for name in ("password_reset_tokens", "email_verification"):
        op.drop_index(f"ix_{name}_token_hash", table_name=name)
        op.drop_index(f"ix_{name}_user_id", table_name=name)
        op.drop_table(name)
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
