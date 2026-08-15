"""副作用幂等：timeout/重放不得重复 promote / billing。"""

from __future__ import annotations

import uuid

import redis.asyncio as redis

from app.core.config import settings

_KEY = "forge:side:{run_id}:{node}:{execution_id}:{operation}"


def side_effect_key(
    run_id: uuid.UUID,
    node: str,
    execution_id: str,
    operation: str,
) -> str:
    return _KEY.format(
        run_id=run_id,
        node=node,
        execution_id=execution_id,
        operation=operation,
    )


async def try_begin_side_effect(
    r: redis.Redis,
    key: str,
    *,
    ttl_s: int | None = None,
) -> bool:
    """首次返回 True；已执行过返回 False。Flag 关闭时始终 True（兼容旧路径）。"""
    if not settings.reliability_idempotent_side_effects:
        return True
    ttl = ttl_s if ttl_s is not None else settings.create_run_idempotency_ttl
    ok = await r.set(key, "1", nx=True, ex=max(1, ttl))
    return bool(ok)


async def already_applied(r: redis.Redis, key: str) -> bool:
    if not settings.reliability_idempotent_side_effects:
        return False
    return bool(await r.exists(key))
