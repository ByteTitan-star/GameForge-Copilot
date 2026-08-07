"""run 控制面：用户暂停/取消通过 Redis 标志；节点间检查。"""

import uuid

import redis.asyncio as redis

_KEY = "run:ctrl:{run_id}"


async def request_pause(r: redis.Redis, run_id: uuid.UUID) -> None:
    await r.set(_KEY.format(run_id=run_id), "pause", ex=86400)


async def request_cancel(r: redis.Redis, run_id: uuid.UUID) -> None:
    await r.set(_KEY.format(run_id=run_id), "cancel", ex=86400)


async def clear_control(r: redis.Redis, run_id: uuid.UUID) -> None:
    await r.delete(_KEY.format(run_id=run_id))


async def poll_control(r: redis.Redis, run_id: uuid.UUID) -> str | None:
    """返回 'pause' | 'cancel' | None。"""
    v = await r.get(_KEY.format(run_id=run_id))
    return v if v in ("pause", "cancel") else None
