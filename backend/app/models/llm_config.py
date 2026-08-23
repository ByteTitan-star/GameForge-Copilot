import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin


class UserLLMConfig(Base, TimestampMixin):
    """用户自备 LLM 配置（provider/model/加密 apikey）。

    场景：Forge 生成时 call_llm 选用、llm_config API。
    """

    __tablename__ = "user_llm_config"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(16))  # LLMProvider value
    model: Mapped[str] = mapped_column(String(128))
    # Fernet 密文，明文不落库（docs/05）
    apikey_enc: Mapped[str] = mapped_column(Text)
    # openai_compat 必填；其余 provider 为 None
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
