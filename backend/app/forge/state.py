"""Run checkpoint persistence.

PostgreSQL is the durable source of truth. Redis remains a best-effort cache so a
Redis restart cannot discard an in-progress HITL interaction.
Cache payload includes revision so load_state can reject stale Redis phantoms (ADR-10).
"""

import json
import logging
import uuid
from typing import Any

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run_checkpoint import RunCheckpoint

_KEY = "run:ckpt:{run_id}"
log = logging.getLogger(__name__)


def _cache_payload(revision: int, state: dict[str, Any]) -> str:
    """将 revision 与 state 序列化为 Redis 缓存 JSON。

    场景：``save_state`` / ``load_state`` 写入 Redis 缓存。
    参数：revision - checkpoint 版本号；state - checkpoint dict。
    返回：JSON 字符串。
    """
    return json.dumps(
        {"revision": int(revision), "state": state},
        ensure_ascii=False,
    )


def _parse_cache(raw: str | bytes) -> tuple[int | None, dict[str, Any] | None]:
    """解析 Redis 缓存中的 checkpoint 数据。

    场景：``load_state`` 读取 Redis 并与 DB revision 对齐。
    参数：raw - Redis 返回的 JSON 字节或字符串。
    返回：(revision, state) 元组；legacy 裸 dict 时 revision 为 None。
    """
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None, None
    if isinstance(data, dict) and "state" in data and "revision" in data:
        state = data.get("state")
        if isinstance(state, dict):
            try:
                return int(data["revision"]), state
            except (TypeError, ValueError):
                return None, None
    # Legacy: bare state dict without revision wrapper
    if isinstance(data, dict):
        return None, data
    return None, None


async def save_state(
    r: redis.Redis, run_id: uuid.UUID, state: dict, db: AsyncSession | None = None
) -> None:
    """持久化 run checkpoint 到 PostgreSQL 并 best-effort 写 Redis 缓存。

    场景：graph 节点间保存 HITL 中断状态；``enqueue_resume`` 写入 resume_grant。
    参数：r - Redis 客户端；run_id - 生成任务 ID；state - checkpoint dict；db - 可选 DB 会话。
    返回：无；run 已结束时跳过写入。
    """
    revision = 1
    if db is not None:
        from app.models.generation_run import GenerationRun

        run = await db.get(GenerationRun, run_id)
        if run is not None and run.ended_at is not None:
            return
        row = await db.get(RunCheckpoint, run_id)
        if row is None:
            row = RunCheckpoint(run_id=run_id, state=state, revision=1)
            db.add(row)
        else:
            row.state = state
            row.revision += 1
        revision = int(row.revision)
        if run is not None:
            run.checkpoint_ref = f"db:run_checkpoints:{run_id}"
        await db.flush()
    try:
        await r.set(_KEY.format(run_id=run_id), _cache_payload(revision, state))
    except Exception:
        if db is None:
            raise
        log.warning("checkpoint cache write failed run_id=%s", run_id, exc_info=True)


async def load_state(
    r: redis.Redis, run_id: uuid.UUID, db: AsyncSession | None = None
) -> dict | None:
    """加载 run checkpoint，PostgreSQL 为权威源，Redis 为 best-effort 缓存。

    场景：resume 前恢复 HITL 状态；``enqueue_resume`` 读取 phase/replan_count。
    参数：r - Redis 客户端；run_id - 生成任务 ID；db - 可选 DB 会话。
    返回：checkpoint dict；不存在时返回 None。revision 不一致时以 DB 为准并回填缓存。
    """
    try:
        raw = await r.get(_KEY.format(run_id=run_id))
    except Exception:
        raw = None
        if db is None:
            raise
        log.warning("checkpoint cache read failed run_id=%s", run_id, exc_info=True)

    cached_rev: int | None = None
    cached_state: dict[str, Any] | None = None
    if raw:
        cached_rev, cached_state = _parse_cache(raw)

    if db is None:
        return cached_state

    row = await db.get(RunCheckpoint, run_id)
    if row is None:
        return cached_state

    db_state = dict(row.state)
    db_rev = int(row.revision)
    if cached_state is not None and cached_rev == db_rev:
        return cached_state

    # Redis missing, legacy, or revision mismatch → DB is SoT
    try:
        await r.set(_KEY.format(run_id=run_id), _cache_payload(db_rev, db_state))
    except Exception:
        log.warning("checkpoint cache refill failed run_id=%s", run_id, exc_info=True)
    return db_state


async def clear_state(r: redis.Redis, run_id: uuid.UUID, db: AsyncSession | None = None) -> None:
    """删除 run checkpoint（DB 行 + Redis 缓存）。

    场景：run 完成或取消后清理；测试 teardown。
    参数：r - Redis 客户端；run_id - 生成任务 ID；db - 可选 DB 会话。
    返回：无。
    """
    if db is not None:
        row = await db.get(RunCheckpoint, run_id)
        if row is not None:
            await db.delete(row)
        from app.models.generation_run import GenerationRun

        run = await db.get(GenerationRun, run_id)
        if run is not None:
            run.checkpoint_ref = None
        await db.flush()
    try:
        await r.delete(_KEY.format(run_id=run_id))
    except Exception:
        if db is None:
            raise
        log.warning("checkpoint cache delete failed run_id=%s", run_id, exc_info=True)
