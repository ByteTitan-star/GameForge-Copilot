import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import GameStatus


class GameCreate(BaseModel):
    """GameCreate 数据传输对象。

    场景：API 或内部序列化契约。"""

    title: str | None = None
    requirement: str | None = None
    template_id: str | None = None


class GamePatch(BaseModel):
    """草稿重命名等（docs/01 MVP）。"""

    title: str | None = None


class GameResp(BaseModel):
    """GameResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    status: GameStatus
    current_version: int
    created_at: datetime


class GameListItem(BaseModel):
    """GameListItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    title: str
    status: GameStatus
    current_version: int
    slug: str | None = None
    cover_url: str | None = None
    updated_at: datetime


class VersionItem(BaseModel):
    """VersionItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

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
    """PreviewTokenResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    preview_url: str
    expires_in_s: int = Field(description="token 有效期（秒）")


class GameDetailResp(BaseModel):
    """GameDetailResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

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
    """GameDeleteResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    deleted: bool = True


class GameBatchDeleteItem(BaseModel):
    """GameBatchDeleteItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    reason: str


class GameBatchDeleteReq(BaseModel):
    """GameBatchDeleteReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    game_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class GameBatchDeleteResp(BaseModel):
    """GameBatchDeleteResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    deleted: list[uuid.UUID]
    failed: list[GameBatchDeleteItem]


class PublicGameItem(BaseModel):
    """PublicGameItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    title: str
    slug: str
    cover_url: str | None = None
    published_at: datetime | None
    play_count: int
