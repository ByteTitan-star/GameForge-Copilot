import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import GameStatus
from app.schemas.game import PublicGameItem


class CreatorBrief(BaseModel):
    handle: str | None = None
    display_name: str | None = None


class PublicGameMeta(PublicGameItem):
    like_count: int = 0
    favorite_count: int = 0
    creator: CreatorBrief | None = None


class ReactionStateResp(BaseModel):
    game_id: uuid.UUID
    liked: bool
    favorited: bool
    like_count: int
    favorite_count: int


class ReactionToggleResp(BaseModel):
    game_id: uuid.UUID
    active: bool
    like_count: int
    favorite_count: int


class FavoriteGameItem(BaseModel):
    game_id: uuid.UUID
    title: str
    slug: str
    status: GameStatus
    play_count: int
    favorited_at: datetime
