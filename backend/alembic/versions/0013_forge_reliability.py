"""0013: Forge checkpoint、任务 outbox 与数据库级请求幂等。"""

import sqlalchemy as sa

from alembic import op

revision = "0013_forge_reliability"
down_revision = "0012_publish_active_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("client_request_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_generation_run_user_request",
        "generation_runs",
        ["user_id", "client_request_id"],
    )
    op.create_table(
        "run_checkpoints",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "task_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_outbox_task", "task_outbox", ["task"])
    op.create_index("ix_task_outbox_next_attempt_at", "task_outbox", ["next_attempt_at"])
    op.create_index("ix_task_outbox_published_at", "task_outbox", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_task_outbox_published_at", table_name="task_outbox")
    op.drop_index("ix_task_outbox_next_attempt_at", table_name="task_outbox")
    op.drop_index("ix_task_outbox_task", table_name="task_outbox")
    op.drop_table("task_outbox")
    op.drop_table("run_checkpoints")
    op.drop_constraint(
        "uq_generation_run_user_request", "generation_runs", type_="unique"
    )
    op.drop_column("generation_runs", "client_request_id")
