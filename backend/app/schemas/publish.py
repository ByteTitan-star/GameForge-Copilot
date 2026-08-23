import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import GameStatus, PublishStatus


class PublishSubmitReq(BaseModel):
    """PublishSubmitReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    version: int
    note: str | None = None


class PublishSubmitResp(BaseModel):
    """PublishSubmitResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    publish_request_id: uuid.UUID
    status: PublishStatus
    game_id: uuid.UUID
    version: int


class PublishQueueItem(BaseModel):
    """PublishQueueItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    publish_request_id: uuid.UUID
    game_id: uuid.UUID
    game_title: str
    version: int
    status: PublishStatus
    created_at: datetime


class GameRef(BaseModel):
    """GameRef 数据传输对象。

    场景：API 或内部序列化契约。"""

    game_id: uuid.UUID
    slug: str | None = None
    status: GameStatus


class PublishApproveResp(BaseModel):
    """PublishApproveResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    publish_request_id: uuid.UUID
    status: PublishStatus
    game: GameRef


class PublishRejectReq(BaseModel):
    """PublishRejectReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    reason: str


class PublishRejectResp(BaseModel):
    """PublishRejectResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    publish_request_id: uuid.UUID
    status: PublishStatus
    game: GameRef


class TakeDownReq(BaseModel):
    """TakeDownReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    reason: str


class TakeDownResp(BaseModel):
    """TakeDownResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    status: GameStatus
    reason: str
