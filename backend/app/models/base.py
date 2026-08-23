from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，Alembic env.py 读其 metadata。"""

    pass


class TimestampMixin:
    """ORM 时间戳混入：created_at / updated_at 自动维护。

    场景：多数业务表继承，记录创建与更新时间。
    """

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
