"""Dev-only runtime debug request/response schemas."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

RedisScope = Literal[
    "forge",
    "usage",
    "analytics",
    "rate_limits",
    "quota",
    "dev_helpers",
    "models_cache",
    "refresh_tokens",
    "all_ephemeral",
    "pattern",
]


class RedisFlushReq(BaseModel):
    scopes: list[RedisScope] = Field(min_length=1)
    run_id: UUID | None = None
    pattern: str | None = Field(
        default=None,
        description="Required when scopes includes 'pattern', e.g. run:events:*",
    )
    confirm: str = Field(description='Must be "FLUSH" to execute destructive ops')


class RedisFlushResp(BaseModel):
    deleted: dict[str, int]


class QueueStatsResp(BaseModel):
    backend: str
    queue: str
    messages: int
    consumers: int | None = None


class QueuePurgeResp(BaseModel):
    backend: str
    queue: str
    purged: int


class RuntimeStatusResp(BaseModel):
    env: str
    messaging_backend: str
    redis: dict[str, int]
    queue: QueueStatsResp


class DevRequeueResp(BaseModel):
    run_id: UUID
    task: str
    status: str
    phase: str | None = None
