"""用户长期偏好 v2（ADR-16：闭集目录 + LRU 归档）。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base


class UserPreferenceV2(Base):
    """偏好身份 = (user_id, preference_key)，key 为目录槽位 id（闭集）。

    归档（status=archived）= agent 永不可见，仅供维护审计；本表不做物理删除。
    note 只写不读：触发语句截断摘录，供管理后台审计，绝不进入注入路径。
    """

    __tablename__ = "user_preferences_v2"
    __table_args__ = (
        UniqueConstraint("user_id", "preference_key", name="uq_user_pref_v2_user_key"),
        Index("ix_user_pref_v2_user_status_lru", "user_id", "status", "last_used_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    preference_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    value_type: Mapped[str] = mapped_column(String(8), nullable=False, default="enum")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="explicit")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
