"""定时上下架扫描（B8）。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import GameStatus, Role
from app.models.game import Game
from app.models.user import User
from app.publish import services as publish_services


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
