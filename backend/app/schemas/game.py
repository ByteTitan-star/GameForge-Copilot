import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import GameStatus


class GameCreate(BaseModel):
    title: str
    requirement: str


class GamePatch(BaseModel):
    """草稿重命名等（docs/01 MVP）。"""

    title: str | None = None


class GameResp(BaseModel):
    game_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    status: GameStatus
    current_version: int
    created_at: datetime


class GameListItem(BaseModel):
    game_id: uuid.UUID
    title: str
    status: GameStatus
    current_version: int
    slug: str | None = None
    updated_at: datetime


class VersionItem(BaseModel):
    version: int
    artifact_path: str
    created_at: datetime


class GameDetailResp(BaseModel):
    game_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    status: GameStatus
    current_version: int
    slug: str | None = None
    versions: list[VersionItem]
    created_at: datetime
    updated_at: datetime


class GameDeleteResp(BaseModel):
    game_id: uuid.UUID
    deleted: bool = True
