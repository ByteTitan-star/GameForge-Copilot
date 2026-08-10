"""Development-only helpers: Redis flush, RabbitMQ queue purge, stuck run requeue."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import RunStatus
from app.forge import control as run_ctrl
from app.forge import queue as forge_queue
from app.forge import state as ckpt
from app.messaging.factory import use_memory
from app.messaging.memory import MemoryTaskPublisher
from app.messaging.rabbit import purge_task_queue, task_queue_stats
from app.messaging.tasks import TASK_QUEUE
from app.models.generation_run import GenerationRun
from app.schemas.dev_runtime import RedisScope

# Prefix groups for selective purge (dev debugging).
_REDIS_PREFIXES: dict[RedisScope, tuple[str, ...]] = {
    "forge": ("run:events:", "run:ckpt:", "run:ctrl:", "run:hitl:"),
    "usage": ("usage:",),
    "analytics": ("play:pv:", "play:uv:"),
    "rate_limits": ("rl:",),
    "quota": ("quota:",),
    "dev_helpers": ("dev:verify:", "oauth:state:"),
    "models_cache": ("models:",),
    "refresh_tokens": ("refresh:",),
}

_ALL_EPHEMERAL: tuple[RedisScope, ...] = (
    "forge",
    "usage",
    "analytics",
    "rate_limits",
    "quota",
    "dev_helpers",
    "models_cache",
)

_HITL_PHASES = frozenset({"plan_confirm", "sandbox_failed", "qa_failed", "user_pause"})
_RETRY_PHASES = frozenset({"sandbox_failed", "qa_failed"})


def _expand_scopes(
    scopes: Iterable[RedisScope], *, run_id: uuid.UUID | None, pattern: str | None
) -> list[str]:
    """Map logical scopes to Redis SCAN match patterns."""
    patterns: list[str] = []
    for scope in scopes:
        if scope == "all_ephemeral":
            for sub in _ALL_EPHEMERAL:
                patterns.extend(_patterns_for_scope(sub, run_id=run_id, pattern=pattern))
            continue
        patterns.extend(_patterns_for_scope(scope, run_id=run_id, pattern=pattern))
    # Preserve order while dropping duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _patterns_for_scope(
    scope: RedisScope, *, run_id: uuid.UUID | None, pattern: str | None
) -> list[str]:
    if scope == "pattern":
        if not pattern:
            raise AppError(ErrorCode.VALIDATION_ERROR, "pattern scope requires pattern field")
        return [pattern]
    if scope == "forge" and run_id is not None:
        rid = str(run_id)
        return [
            f"run:events:{rid}",
            f"run:ckpt:{rid}",
            f"run:ctrl:{rid}",
            f"run:hitl:{rid}",
        ]
    prefixes = _REDIS_PREFIXES.get(scope)
    if prefixes is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"unknown redis scope: {scope}")
    return [f"{p}*" for p in prefixes]


async def count_redis_prefixes(r: redis.Redis) -> dict[str, int]:
    """Count keys per dev scope (approximate via SCAN)."""
    counts: dict[str, int] = {}
    for scope in (*_ALL_EPHEMERAL, "refresh_tokens"):
        n = 0
        for pat in _patterns_for_scope(scope, run_id=None, pattern=None):
            async for _key in r.scan_iter(match=pat, count=200):
                n += 1
        counts[scope] = n
    return counts


async def flush_redis(
    r: redis.Redis,
    scopes: list[RedisScope],
    *,
    run_id: uuid.UUID | None,
    pattern: str | None,
) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for pat in _expand_scopes(scopes, run_id=run_id, pattern=pattern):
        n = 0
        async for key in r.scan_iter(match=pat, count=200):
            await r.delete(key)
            n += 1
        deleted[pat] = n
    return deleted


async def get_queue_stats() -> dict[str, int | str | None]:
    if use_memory():
        return {
            "backend": "memory",
            "queue": TASK_QUEUE,
            "messages": len(MemoryTaskPublisher.captured),
            "consumers": None,
        }
    stats = await task_queue_stats()
    return {"backend": "rabbitmq", **stats}


async def purge_queue() -> dict[str, int | str]:
    if use_memory():
        n = len(MemoryTaskPublisher.captured)
        MemoryTaskPublisher.reset()
        return {"backend": "memory", "queue": TASK_QUEUE, "purged": n}
    purged = await purge_task_queue()
    return {"backend": "rabbitmq", "queue": TASK_QUEUE, "purged": purged}


async def get_runtime_status(r: redis.Redis) -> dict:
    redis_counts = await count_redis_prefixes(r)
    queue = await get_queue_stats()
    return {
        "env": settings.env,
        "messaging_backend": settings.messaging_backend,
        "redis": redis_counts,
        "queue": queue,
    }


async def dev_requeue_run(db: AsyncSession, r: redis.Redis, run_id: uuid.UUID) -> dict:
    """Re-enqueue a stuck run after worker restart (dev only)."""
    run = await db.get(GenerationRun, run_id)
    if run is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "run 不存在")

    if run.status == RunStatus.DONE.value:
        raise AppError(ErrorCode.INVALID_STATE, "run 已完成，不可 requeue")

    state = await ckpt.load_state(r, run_id) or {}
    phase = state.get("phase")
    if isinstance(phase, str):
        phase_str: str | None = phase
    else:
        phase_str = None

    await run_ctrl.clear_control(r, run_id)
    await r.delete(f"run:hitl:{run_id}")

    if run.status == RunStatus.PAUSED.value:
        run.status = RunStatus.RUNNING.value
        await db.commit()
        await forge_queue.enqueue_resume(run_id, "approve", None)
        return {
            "run_id": run_id,
            "task": "resume_run",
            "status": run.status,
            "phase": phase_str,
        }

    if run.status == RunStatus.RUNNING.value:
        if state:
            await forge_queue.enqueue_resume(run_id, "approve", None)
            task = "resume_run"
        else:
            await forge_queue.enqueue_run(run_id)
            task = "execute_run"
        return {
            "run_id": run_id,
            "task": task,
            "status": run.status,
            "phase": phase_str,
        }

    if run.status == RunStatus.FAILED.value:
        if phase_str not in _RETRY_PHASES and phase_str not in _HITL_PHASES:
            raise AppError(ErrorCode.INVALID_STATE, "failed run 无可用检查点，不可 requeue")
        run.status = RunStatus.RUNNING.value
        run.ended_at = None
        await db.commit()
        await forge_queue.enqueue_resume(run_id, "approve", None)
        return {
            "run_id": run_id,
            "task": "resume_run",
            "status": run.status,
            "phase": phase_str,
        }

    raise AppError(ErrorCode.INVALID_STATE, f"run status={run.status} 不可 requeue")


async def reset_dev_state(db: AsyncSession, r: redis.Redis) -> dict:
    """一键清本地 dev 的 forge 运行态（dev only）。

    组合三步，用于本地调试想要干净状态时：
        1. 把所有 running/paused 的 run 置 failed + ended_at（顶部「等待确认」banner 的源头）。
        2. 清掉所有 run 的 forge Redis 键（events/ckpt/ctrl/hitl，含已 failed run 的残留缓冲）。
        3. 清空任务队列里残留的 execute_run/resume_run 消息。
    已 failed 的 run 不受 DB 改动影响；终态守卫保证残留消息不会复活它们。
    """
    active_ids = (
        (
            await db.scalars(
                select(GenerationRun.id).where(
                    GenerationRun.status.in_(
                        [RunStatus.RUNNING.value, RunStatus.PAUSED.value]
                    )
                )
            )
        )
        .all()
        .copy()
    )
    if active_ids:
        await db.execute(
            update(GenerationRun)
            .where(GenerationRun.id.in_(active_ids))
            .values(status=RunStatus.FAILED.value, ended_at=datetime.now(UTC))
        )
        await db.commit()
    redis_deleted = await flush_redis(r, ["forge"], run_id=None, pattern=None)
    queue = await purge_queue()
    return {
        "failed_runs": active_ids,
        "failed_count": len(active_ids),
        "redis_deleted": redis_deleted,
        "queue": queue,
    }
