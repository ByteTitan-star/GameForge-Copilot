"""副作用幂等：timeout/重放不得重复 promote / billing。

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
节点超时或 worker 重投时，同一「副作用」可能被执行两次。
用 Redis SET NX 做一次性标记，典型流程：

  key = side_effect_key(run, node, execution_id, operation)
  if not await try_begin_side_effect(r, key):  # 已有人做过
      return  # 跳过重复 promote / 扣费
  ... 执行副作用（写 DB）...
  await commit_side_effect(r, key)  # 标记 done

开关：settings.reliability_idempotent_side_effects=False 时全部放行（开发便利）。
主图 promote / HITL 提交等路径会调用本模块（见 graph._commit_hitl_side_effects）。
"""

from __future__ import annotations

import uuid

import redis.asyncio as redis

from app.core.config import settings

# Redis key 模板：把 run / 节点 / 本次执行 id / 操作名绑死，避免串味
_KEY = "forge:side:{run_id}:{node}:{execution_id}:{operation}"


def side_effect_key(
    run_id: uuid.UUID,
    node: str,
    execution_id: str,
    operation: str,
) -> str:
    """构造幂等键。operation 例：promote、billing、hitl_commit。"""
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
    """尝试「开始」副作用：首次返回 True 并写入 value；已执行过返回 False。

    Flag 关闭时始终 True（不做幂等）。
    写入值常用 "1"（进行中）或业务自定义；成功后应 commit_side_effect → "done"。
    """
    if not settings.reliability_idempotent_side_effects:
        return True
    ttl = ttl_s if ttl_s is not None else settings.create_run_idempotency_ttl
    ok = await r.set(key, value, nx=True, ex=max(1, ttl))
    return bool(ok)


async def get_side_effect_value(r: redis.Redis, key: str) -> str | None:
    """读取幂等键当前值；关闭开关时返回 None。"""
    if not settings.reliability_idempotent_side_effects:
        return None
    raw = await r.get(key)
    return str(raw) if raw is not None else None


async def side_effect_status(r: redis.Redis, key: str) -> str | None:
    """返回 pending(任意非 done) / done / 其它原始值；无键则 None。"""
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
    """是否已经成功应用过（done 或历史值 "1" 都视为已应用）。"""
    if not settings.reliability_idempotent_side_effects:
        return False
    status = await side_effect_status(r, key)
    return status == "done" or status == "1"
