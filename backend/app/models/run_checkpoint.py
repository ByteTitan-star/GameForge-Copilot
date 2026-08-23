import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base


class RunCheckpoint(Base):
    """LangGraph checkpoint 持久化（PostgreSQL 侧镜像）。

    场景：state 冷启动、跨 worker 恢复图状态。
    """

    __tablename__ = "run_checkpoints"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("generation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
