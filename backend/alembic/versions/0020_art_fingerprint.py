"""0020: ArtifactRevision art dependency fingerprint columns."""

import sqlalchemy as sa

from alembic import op

revision = "0020_art_fingerprint"
down_revision = "0019_artifact_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifact_revisions",
        sa.Column("dependency_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "artifact_revisions",
        sa.Column("fingerprint_version", sa.String(length=48), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artifact_revisions", "fingerprint_version")
    op.drop_column("artifact_revisions", "dependency_fingerprint")
