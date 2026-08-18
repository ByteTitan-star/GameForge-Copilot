import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.enums import ArtifactStatus
from app.models.base import Base


class ArtifactRevision(Base):
    __tablename__ = "artifact_revisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ArtifactStatus.ACTIVE.value
    )
    stale_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    supersedes: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    plan_revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    art_revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    candidate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependency_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_version: Mapped[str | None] = mapped_column(String(48), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
