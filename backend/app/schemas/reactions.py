import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import GameStatus
from app.schemas.game import PublicGameItem


class CreatorBrief(BaseModel):
    """CreatorBrief 数据传输对象。

    场景：API 或内部序列化契约。"""

    handle: str | None = None
    display_name: str | None = None


class PublicGameMeta(PublicGameItem):
    """PublicGameMeta 数据传输对象。

    场景：API 或内部序列化契约。"""

    featured: bool = False
    like_count: int = 0
    favorite_count: int = 0
    creator: CreatorBrief | None = None


class ReactionStateResp(BaseModel):
    """ReactionStateResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    liked: bool
    favorited: bool
    like_count: int
    favorite_count: int


class ReactionToggleResp(BaseModel):
    """ReactionToggleResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    active: bool
    like_count: int
    favorite_count: int


class FavoriteGameItem(BaseModel):
    """FavoriteGameItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    title: str
    slug: str
    status: GameStatus
    play_count: int
    favorited_at: datetime
