import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.enums import GameStatus
from app.models.base import Base, TimestampMixin


class Game(Base, TimestampMixin):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default=GameStatus.DRAFT.value)
    current_version: Mapped[int] = mapped_column(Integer, default=0)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_take_down_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    featured_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 当前封面图（镜像 current_version 的 thumbnail_path）。None 时卡片回退渐变。
    # 冗余在 Game 表避免列表 join 版本表；qa_node 截图成功与 activate_version 时同步。
    cover_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
