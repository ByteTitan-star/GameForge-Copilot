import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base


class FailureReport(Base):
    """Run 失败结构化报告（分类、诊断、证据链）。

    场景：QA/构建失败后归档、离线分析。
    """

    __tablename__ = "failure_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("generation_runs.id", ondelete="CASCADE"), index=True
    )
    plan_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    art_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_class: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_source: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    failure_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attempts: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    diagnosis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    resource_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
