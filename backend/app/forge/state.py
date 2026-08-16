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
    try:
        await r.set(_KEY.format(run_id=run_id), _cache_payload(revision, state))
    except Exception:
        if db is None:
            raise
        log.warning("checkpoint cache write failed run_id=%s", run_id, exc_info=True)


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
