"""code-review 修复：user_llm_config.base_url 列（openai_compat 必填）

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_llm_config", sa.Column("base_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("user_llm_config", "base_url")
