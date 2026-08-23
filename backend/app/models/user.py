import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.enums import Role
from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """平台用户账号（邮箱登录、OAuth、角色与创作者资料）。

    场景：认证、配额、游戏 owner、admin 操作主体。
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # StrEnum 以 value 字符串存储，比较 `user.role == Role.ADMIN` 仍成立
    role: Mapped[str] = mapped_column(String(16), default=Role.USER.value)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    handle: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_public: Mapped[bool] = mapped_column(Boolean, default=True)
