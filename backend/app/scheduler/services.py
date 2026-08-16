"""定时上下架扫描（B8）+ HIL/暂停等待超时回收。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from app.core.config import settings
from app.enums import GameStatus, Role, RunStatus, WSEventType
from app.forge import state as ckpt
from app.forge.events import publish_event
from app.forge.messages import add_message
from app.messaging.outbox import cancel_run_tasks
from app.models.game import Game
from app.models.generation_run import GenerationRun
from app.models.user import User
from app.publish import services as publish_services
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _pick_admin(db: AsyncSession) -> User | None:
    return await db.scalar(select(User).where(User.role == Role.ADMIN.value).limit(1))


async def scan_scheduled(db: AsyncSession) -> int:
    """执行到期的定时上下架，返回处理数量。"""
    now = datetime.now(UTC)
    admin = await _pick_admin(db)
    if admin is None:
        return 0
    count = await _run_take_downs(db, admin, now)
    count += await _run_republishes(db, admin, now)
    if count:
        await db.commit()
    return count


async def expire_stale_paused_runs(db: AsyncSession, r: redis.Redis | None = None) -> int:
    """将超过 hil_wait_timeout_s 仍处于 PAUSED 的 run 置为 FAILED，释放并发额度。

    判定依据：status=paused 且 updated_at 早于 cutoff（暂停写入时会刷新 updated_at）。
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.hil_wait_timeout_s)
    rows = (
        await db.scalars(
            select(GenerationRun).where(
                GenerationRun.status == RunStatus.PAUSED.value,
                GenerationRun.ended_at.is_(None),
                GenerationRun.updated_at <= cutoff,
            )
        )
    ).all()
    if not rows:
        return 0

    now = datetime.now(UTC)
    if settings.hil_wait_timeout_s >= 3600 and settings.hil_wait_timeout_s % 3600 == 0:
        wait_label = f"{settings.hil_wait_timeout_s // 3600} 小时"
    else:
        wait_label = f"{settings.hil_wait_timeout_s} 秒"
    msg = f"等待确认已超过 {wait_label}，本轮生成已自动结束以释放并发额度。"
    for run in rows:
        await _fail_stale_run(
            db,
            r,
            run,
            now=now,
            code="HIL_TIMEOUT",
            message=msg,
        )
    await db.commit()
    return len(rows)


async def expire_stale_running_runs(db: AsyncSession, r: redis.Redis | None = None) -> int:
    """回收租约丢失且长时间无更新的 RUNNING run（ADR-10）。"""
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.running_stale_timeout_s)
    rows = (
        await db.scalars(
            select(GenerationRun).where(
                GenerationRun.status == RunStatus.RUNNING.value,
                GenerationRun.ended_at.is_(None),
                GenerationRun.updated_at <= cutoff,
            )
        )
    ).all()
    if not rows:
        return 0

    now = datetime.now(UTC)
    msg = "执行租约已丢失且长时间无进度，本轮生成已自动结束以释放并发额度。"
    count = 0
    for run in rows:
        if r is not None and await r.exists(f"run:executing:{run.id}"):
            continue
        await _fail_stale_run(
            db,
            r,
            run,
            now=now,
            code="RUNNING_STALE",
            message=msg,
        )
        count += 1
    if count:
        await db.commit()
    return count


async def _fail_stale_run(
    db: AsyncSession,
    r: redis.Redis | None,
    run: GenerationRun,
    *,
    now: datetime,
    code: str,
    message: str,
) -> None:
    run.status = RunStatus.FAILED.value
    run.ended_at = now
    await add_message(
        db,
        game_id=run.game_id,
        run_id=run.id,
        user_id=run.user_id,
        role="system",
        kind="failed",
        content=message,
        metadata={"code": code},
        dedupe_key=f"{run.id}:failed:{code}",
    )
    await cancel_run_tasks(db, run.id)
    if r is not None:
        await ckpt.clear_state(r, run.id, db)
        await r.delete(f"run:hitl:{run.id}")
    await publish_event(
        run.id,
        WSEventType.ERROR,
        {"code": code, "message": message, "fatal": True},
    )


async def _run_take_downs(db: AsyncSession, admin: User, now: datetime) -> int:
    """到期 scheduled_take_down_at：PUBLISHED → TAKEN_DOWN。"""
    rows = (
        await db.scalars(
            select(Game).where(
                Game.scheduled_take_down_at.is_not(None),
                Game.scheduled_take_down_at <= now,
                Game.status == GameStatus.PUBLISHED.value,
            )
        )
    ).all()
    count = 0
    for game in rows:
        gid = game.id
        await publish_services.take_down(db, admin, gid, reason="定时下架到期自动执行")
        refreshed = await db.get(Game, gid)
        if refreshed is not None:
            refreshed.scheduled_take_down_at = None
        count += 1
    return count


async def _run_republishes(db: AsyncSession, admin: User, now: datetime) -> int:
    """到期 scheduled_publish_at：TAKEN_DOWN → PUBLISHED。"""
    rows = (
        await db.scalars(
            select(Game).where(
                Game.scheduled_publish_at.is_not(None),
                Game.scheduled_publish_at <= now,
                Game.status == GameStatus.TAKEN_DOWN.value,
            )
        )
    ).all()
    count = 0
    for game in rows:
        gid = game.id
        await publish_services.republish(db, admin, gid, reason="定时上架到期自动执行")
        refreshed = await db.get(Game, gid)
        if refreshed is not None:
            refreshed.scheduled_publish_at = None
        count += 1
    return count
