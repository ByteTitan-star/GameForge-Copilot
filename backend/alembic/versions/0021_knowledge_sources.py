"""0021: knowledge_sources table for ADR-14 two-tier archive."""

import sqlalchemy as sa

from alembic import op

revision = "0021_knowledge_sources"
down_revision = "0020_art_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_ptr", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("locale", sa.String(length=16), nullable=False, server_default="zh-CN"),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backend", sa.String(length=16), nullable=False, server_default="local"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "document_id",
            "content_hash",
            name="uq_knowledge_sources_src_doc_hash",
        ),
    )
    op.create_index("ix_knowledge_sources_source_id", "knowledge_sources", ["source_id"])
    op.create_index("ix_knowledge_sources_document_id", "knowledge_sources", ["document_id"])
    op.create_index("ix_knowledge_sources_content_hash", "knowledge_sources", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_sources_content_hash", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_document_id", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_source_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
