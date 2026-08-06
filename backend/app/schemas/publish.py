import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import GameStatus, PublishStatus


class PublishSubmitReq(BaseModel):
    version: int
    note: str | None = None


class PublishSubmitResp(BaseModel):
    publish_request_id: uuid.UUID
    status: PublishStatus
    game_id: uuid.UUID
    version: int


class PublishQueueItem(BaseModel):
    publish_request_id: uuid.UUID
    game_id: uuid.UUID
    game_title: str
    version: int
    status: PublishStatus
    created_at: datetime


class GameRef(BaseModel):
    game_id: uuid.UUID
    slug: str | None = None
    status: GameStatus


class PublishApproveResp(BaseModel):
    publish_request_id: uuid.UUID
    status: PublishStatus
    game: GameRef


class PublishRejectReq(BaseModel):
    reason: str


class PublishRejectResp(BaseModel):
    publish_request_id: uuid.UUID
    status: PublishStatus
    game: GameRef


class TakeDownReq(BaseModel):
    reason: str


class TakeDownResp(BaseModel):
    game_id: uuid.UUID
    status: GameStatus
    reason: str
