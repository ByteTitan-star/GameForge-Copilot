"""0019: ArtifactRevision lineage — plan/art/candidate 只增不删。"""

import sqlalchemy as sa

from alembic import op

revision = "0019_artifact_revisions"
down_revision = "0018_failure_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stale_reason", sa.String(length=32), nullable=True),
        sa.Column("supersedes", sa.Uuid(), nullable=True),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=True),
        sa.Column("art_revision_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_version", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifact_revisions_run_id", "artifact_revisions", ["run_id"])
    op.create_index(
        "ix_artifact_revisions_run_kind_status",
        "artifact_revisions",
        ["run_id", "kind", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_revisions_run_kind_status", table_name="artifact_revisions")
    op.drop_index("ix_artifact_revisions_run_id", table_name="artifact_revisions")
    op.drop_table("artifact_revisions")
