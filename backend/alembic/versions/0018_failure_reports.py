"""0018: FailureReport Lite — 失败证据在 HITL 前冻结。"""

import sqlalchemy as sa

from alembic import op

revision = "0018_failure_reports"
down_revision = "0017_run_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "failure_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.String(length=64), nullable=True),
        sa.Column("art_revision_id", sa.String(length=64), nullable=True),
        sa.Column("candidate_revision_id", sa.String(length=64), nullable=True),
        sa.Column("failure_class", sa.String(length=32), nullable=False),
        sa.Column("classification_source", sa.String(length=32), nullable=False),
        sa.Column("classification_confidence", sa.Float(), nullable=False),
        sa.Column("failure_stage", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.JSON(), nullable=False),
        sa.Column("diagnosis", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("resource_usage", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_failure_reports_run_id", "failure_reports", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_failure_reports_run_id", table_name="failure_reports")
    op.drop_table("failure_reports")
