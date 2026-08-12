"""Run checkpoint persistence.

PostgreSQL is the durable source of truth. Redis remains a best-effort cache so a
Redis restart cannot discard an in-progress HITL interaction.
"""

import json
import logging
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run_checkpoint import RunCheckpoint

_KEY = "run:ckpt:{run_id}"
log = logging.getLogger(__name__)


async def save_state(
    r: redis.Redis, run_id: uuid.UUID, state: dict, db: AsyncSession | None = None
) -> None:
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
        if run is not None:
            run.checkpoint_ref = f"db:run_checkpoints:{run_id}"
        await db.flush()
    try:
        await r.set(_KEY.format(run_id=run_id), json.dumps(state, ensure_ascii=False))
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
    if raw:
        return json.loads(raw)
    if db is None:
        return None
    row = await db.get(RunCheckpoint, run_id)
    if row is None:
        return None
    state = dict(row.state)
    try:
        await r.set(_KEY.format(run_id=run_id), json.dumps(state, ensure_ascii=False))
    except Exception:
        log.warning("checkpoint cache refill failed run_id=%s", run_id, exc_info=True)
    return state


async def clear_state(
    r: redis.Redis, run_id: uuid.UUID, db: AsyncSession | None = None
) -> None:
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
