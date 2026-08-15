import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import GameStatus


class GameCreate(BaseModel):
    title: str | None = None
    requirement: str | None = None
    template_id: str | None = None


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
    cover_url: str | None = None
    updated_at: datetime


class VersionItem(BaseModel):
    version: int
    artifact_path: str
    thumbnail_path: str | None = None
    created_at: datetime


class ArtifactFileItem(BaseModel):
    """产物单个文件的只读描述（代码预览用）。路径为相对产物根的 POSIX 路径。"""

    path: str
    size: int
    mime: str | None = None


class PreviewTokenResp(BaseModel):
    preview_url: str
    expires_in_s: int = Field(description="token 有效期（秒）")


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


class GameBatchDeleteItem(BaseModel):
    game_id: uuid.UUID
    reason: str


class GameBatchDeleteReq(BaseModel):
    game_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class GameBatchDeleteResp(BaseModel):
    deleted: list[uuid.UUID]
    failed: list[GameBatchDeleteItem]


class PublicGameItem(BaseModel):
    game_id: uuid.UUID
    title: str
    slug: str
    cover_url: str | None = None
    published_at: datetime | None
    play_count: int
