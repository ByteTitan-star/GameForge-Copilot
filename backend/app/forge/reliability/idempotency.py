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
    """构造副作用幂等 Redis 键。

    场景：promote、billing 等写操作前。
    参数：run_id、node、execution_id、operation 名。
    返回：forge:side:... 键字符串。
    """
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
    value: str = "1",
) -> bool:
    """首次返回 True 并写入 value；已执行过返回 False。Flag 关闭时始终 True。"""
    if not settings.reliability_idempotent_side_effects:
        return True
    ttl = ttl_s if ttl_s is not None else settings.create_run_idempotency_ttl
    ok = await r.set(key, value, nx=True, ex=max(1, ttl))
    return bool(ok)


async def get_side_effect_value(r: redis.Redis, key: str) -> str | None:
    """读取副作用键当前值（pending/done）。

    场景：already_applied、状态查询。
    参数：r、key。
    返回：字符串值或 None；关 flag 时恒 None。
    """
    if not settings.reliability_idempotent_side_effects:
        return None
    raw = await r.get(key)
    return str(raw) if raw is not None else None


async def side_effect_status(r: redis.Redis, key: str) -> str | None:
    """返回 pending / done / 其它原始值；无键则 None。"""
    return await get_side_effect_value(r, key)


async def commit_side_effect(
    r: redis.Redis,
    key: str,
    *,
    ttl_s: int | None = None,
) -> None:
    """将副作用标记为已提交（DB commit 成功后调用）。"""
    if not settings.reliability_idempotent_side_effects:
        return
    ttl = ttl_s if ttl_s is not None else settings.create_run_idempotency_ttl
    await r.set(key, "done", ex=max(1, ttl))


async def already_applied(r: redis.Redis, key: str) -> bool:
    """判断副作用是否已成功提交过。

    场景：重复执行节点前跳过写操作。
    参数：r、key。
    返回：status 为 done/1 时为 True。
    """
    if not settings.reliability_idempotent_side_effects:
        return False
    status = await side_effect_status(r, key)
    return status == "done" or status == "1"
