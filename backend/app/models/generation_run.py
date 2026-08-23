import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.enums import RunPhase, RunStatus
from app.models.base import Base, TimestampMixin


class GenerationRun(Base, TimestampMixin):
    """单次 Forge 生成任务（plan→art→code→qa 流水线实例）。

    场景：worker 执行、WS 进度、HITL 暂停与恢复。
    """

    __tablename__ = "generation_runs"

    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_generation_run_user_request"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    llm_config_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_llm_config.id", ondelete="SET NULL"), nullable=True
    )
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry_phase: Mapped[str] = mapped_column(String(8), default="plan")
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.RUNNING.value)
    phase: Mapped[str | None] = mapped_column(String(16), default=RunPhase.PLAN.value)
    checkpoint_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    control_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    workflow_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
