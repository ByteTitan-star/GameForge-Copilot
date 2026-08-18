"""0017: RunCommand 幂等与 HITL control_revision。"""

import sqlalchemy as sa

from alembic import op

revision = "0017_run_commands"
down_revision = "0016_memory_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("control_revision", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_runs",
        sa.Column("workflow_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "run_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("command_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "idempotency_key", name="uq_run_command_idempotency"),
    )
    op.create_index("ix_run_commands_run_id", "run_commands", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_commands_run_id", table_name="run_commands")
    op.drop_table("run_commands")
    op.drop_column("generation_runs", "workflow_version")
    op.drop_column("generation_runs", "control_revision")
