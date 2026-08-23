import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.enums import PublishStatus
from app.models.base import Base, TimestampMixin


class PublishRequest(Base, TimestampMixin):
    """游戏版本提交广场发布的审核单。

    场景：publish API、admin 审批/驳回。
    """

    __tablename__ = "publish_requests"

    # 每个游戏同时只能有一个「待审核」发布申请（submitted/reviewing）。
    # 部分唯一索引：rejected/approved 行不占名额，允许驳回后重新提交。
    # postgresql_where / sqlite_where 双声明，保证 PG 生产与 sqlite 测试一致。
    __table_args__ = (
        Index(
            "uq_publish_active_per_game",
            "game_id",
            unique=True,
            postgresql_where=text("status IN ('submitted', 'reviewing')"),
            sqlite_where=text("status IN ('submitted', 'reviewing')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=PublishStatus.SUBMITTED.value)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
