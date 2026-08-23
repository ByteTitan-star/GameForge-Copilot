import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base, TimestampMixin


class GameVersion(Base, TimestampMixin):
    """游戏某一版本的产物与策划稿快照。

    场景：试玩 URL、版本历史、promote 后 current_version 指向。
    """

    __tablename__ = "game_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # 该版本的封面截图相对路径（如 "thumb.png"）。QA 通过后由 qa_node 截图写入，可能为 NULL。
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    design_doc: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
