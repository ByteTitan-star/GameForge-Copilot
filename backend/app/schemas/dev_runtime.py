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
    """RedisFlushReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    scopes: list[RedisScope] = Field(min_length=1)
    run_id: UUID | None = None
    pattern: str | None = Field(
        default=None,
        description="Required when scopes includes 'pattern', e.g. run:events:*",
    )
    confirm: str = Field(description='Must be "FLUSH" to execute destructive ops')


class RedisFlushResp(BaseModel):
    """RedisFlushResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    deleted: dict[str, int]


class QueueStatsResp(BaseModel):
    """QueueStatsResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    backend: str
    queue: str
    messages: int
    consumers: int | None = None


class QueuePurgeResp(BaseModel):
    """QueuePurgeResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    backend: str
    queue: str
    purged: int


class RuntimeStatusResp(BaseModel):
    """RuntimeStatusResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    env: str
    messaging_backend: str
    redis: dict[str, int]
    queue: QueueStatsResp


class DevRequeueResp(BaseModel):
    """DevRequeueResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    run_id: UUID
    task: str
    status: str
    phase: str | None = None


class DevResetResp(BaseModel):
    """DevResetResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    failed_runs: list[UUID]
    failed_count: int
    redis_deleted: dict[str, int]
    queue: QueuePurgeResp
