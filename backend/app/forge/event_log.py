"""Run WS 事件环形缓冲（Redis），支持刷新/重连后 replay。"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

import redis.asyncio as redis

from app.core.redis import pool

_KEY = "run:events:{run_id}"
_MAX_EVENTS = 200
_TTL_SECONDS = 86400 * 7

_event_redis: ContextVar[redis.Redis | None] = ContextVar("_event_redis", default=None)


def bind_event_redis(client: redis.Redis | None) -> None:
    """Worker / 测试注入与请求相同的 Redis 客户端。"""
    _event_redis.set(client)


async def _client() -> tuple[redis.Redis, bool]:
    bound = _event_redis.get()
    if bound is not None:
        return bound, False
    return redis.Redis(connection_pool=pool), True


async def append_event(r: redis.Redis, run_id: uuid.UUID, data: str) -> None:
    key = _KEY.format(run_id=run_id)
    async with r.pipeline(transaction=True) as pipe:
        pipe.rpush(key, data)
        pipe.ltrim(key, -_MAX_EVENTS, -1)
        pipe.expire(key, _TTL_SECONDS)
        await pipe.execute()


async def list_events(r: redis.Redis, run_id: uuid.UUID) -> list[str]:
    key = _KEY.format(run_id=run_id)
    rows = await r.lrange(key, 0, -1)
    return list(rows or [])


async def list_events_auto(run_id: uuid.UUID) -> list[str]:
    client, owned = await _client()
    try:
        return await list_events(client, run_id)
    finally:
        if owned:
            await client.aclose()


async def clear_events(r: redis.Redis, run_id: uuid.UUID) -> None:
    await r.delete(_KEY.format(run_id=run_id))
