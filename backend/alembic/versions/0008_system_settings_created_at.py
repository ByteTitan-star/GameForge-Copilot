"""system_settings 补 created_at（0005 漏列；已有库需本迁移）

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE system_settings "
            "ADD COLUMN IF NOT EXISTS created_at "
            "TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()"
        )
    )


def downgrade() -> None:
    op.drop_column("system_settings", "created_at")
