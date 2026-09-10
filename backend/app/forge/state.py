"""Run checkpoint persistence.

PostgreSQL is the durable source of truth. Redis remains a best-effort cache so a
Redis restart cannot discard an in-progress HITL interaction.

Write/read ordering (ADR-10 §5, #158):
- With a DB session, the Redis payload is published only after the caller's
  transaction commits (session ``after_commit`` hook); rollback discards the
  pending publish. Redis can therefore fall behind Postgres (stale-but-safe,
  repaired on next load) but never ahead of it with uncommitted state.
- ``load_state`` validates a Redis hit against a revision-only DB query, so a
  cache hit never pays the full JSON ``state`` row read. Remaining window: the
  refill on miss/mismatch may publish uncommitted data read from the *same*
  transaction; readers reject it via the revision check until it commits.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

import redis.asyncio as redis
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run_checkpoint import RunCheckpoint

_KEY = "run:ckpt:{run_id}"
_PENDING = "forge_ckpt_pending"  # session.info key: {run_id: (redis_client, payload)}
log = logging.getLogger(__name__)

# 后台发布任务的强引用，避免被 GC；完成后自动移除
_pending_tasks: set[asyncio.Task] = set()


def _cache_payload(revision: int, state: dict[str, Any]) -> str:
    return json.dumps(
        {"revision": int(revision), "state": state},
        ensure_ascii=False,
    )


def _parse_cache(raw: str | bytes) -> tuple[int | None, dict[str, Any] | None]:
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


async def _publish(r: redis.Redis, run_id: uuid.UUID, payload: str) -> None:
    try:
        await r.set(_KEY.format(run_id=run_id), payload)
    except Exception:
        log.warning("checkpoint cache publish failed run_id=%s", run_id, exc_info=True)


def _on_commit(session) -> None:
    pending: dict | None = session.info.pop(_PENDING, None)
    if not pending:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 无事件循环（AsyncSession 正常不会发生）
        return
    for run_id, (r, payload) in pending.items():
        task = loop.create_task(_publish(r, run_id, payload))
        _pending_tasks.add(task)
        task.add_done_callback(_pending_tasks.discard)


def _on_rollback(session) -> None:
    # 丢弃未提交的发布：Redis 保持旧值（落后于 DB，安全），下次 load 会对账修复
    session.info.pop(_PENDING, None)


def _on_soft_rollback(session, prev_txn) -> None:
    _on_rollback(session)


def _defer_publish(db: AsyncSession, r: redis.Redis, run_id: uuid.UUID, payload: str) -> None:
    sync_session = db.sync_session
    if not sync_session.info.get("forge_ckpt_listeners"):
        event.listen(sync_session, "after_commit", _on_commit)
        event.listen(sync_session, "after_rollback", _on_rollback)
        # savepoint 回滚同样使本事务内的 flush 失效；一并丢弃（宁可不发布，不冒幻影风险）
        event.listen(sync_session, "after_soft_rollback", _on_soft_rollback)
        sync_session.info["forge_ckpt_listeners"] = True
    sync_session.info.setdefault(_PENDING, {})[run_id] = (r, payload)


def _discard_pending(db: AsyncSession, run_id: uuid.UUID) -> None:
    pending: dict | None = db.sync_session.info.get(_PENDING)
    if pending is not None:
        pending.pop(run_id, None)


async def save_state(
    r: redis.Redis, run_id: uuid.UUID, state: dict, db: AsyncSession | None = None
) -> None:
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
        _defer_publish(db, r, run_id, _cache_payload(revision, state))
        return
    # 无 DB 会话：纯缓存模式，直接写入，失败显式抛出（与旧行为一致）
    await r.set(_KEY.format(run_id=run_id), _cache_payload(revision, state))


async def load_state(
    r: redis.Redis, run_id: uuid.UUID, db: AsyncSession | None = None
) -> dict | None:
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

    # 廉价校验：仅查 revision 列，命中且一致时无需加载完整 state 行（#158）
    if cached_state is not None and cached_rev is not None:
        db_rev = (
            await db.scalars(select(RunCheckpoint.revision).where(RunCheckpoint.run_id == run_id))
        ).one_or_none()
        if db_rev is None or cached_rev == db_rev:
            return cached_state

    # Redis missing, legacy, or revision mismatch → DB is SoT
    row = await db.get(RunCheckpoint, run_id)
    if row is None:
        return cached_state

    db_state = dict(row.state)
    db_rev = int(row.revision)
    try:
        await r.set(_KEY.format(run_id=run_id), _cache_payload(db_rev, db_state))
    except Exception:
        log.warning("checkpoint cache refill failed run_id=%s", run_id, exc_info=True)
    return db_state


async def clear_state(r: redis.Redis, run_id: uuid.UUID, db: AsyncSession | None = None) -> None:
    if db is not None:
        row = await db.get(RunCheckpoint, run_id)
        if row is not None:
            await db.delete(row)
        from app.models.generation_run import GenerationRun

        run = await db.get(GenerationRun, run_id)
        if run is not None:
            run.checkpoint_ref = None
        await db.flush()
        # 同事务先 save 后 clear：必须丢弃待发布，否则 commit 后会把已删除的 state 写回 Redis
        _discard_pending(db, run_id)
    try:
        await r.delete(_KEY.format(run_id=run_id))
    except Exception:
        if db is None:
            raise
        log.warning("checkpoint cache delete failed run_id=%s", run_id, exc_info=True)
