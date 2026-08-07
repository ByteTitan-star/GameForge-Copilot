"""定时上下架扫描（B8）。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import GameStatus, Role
from app.models.game import Game
from app.models.user import User
from app.publish import services as publish_services


async def scan_scheduled(db: AsyncSession) -> int:
    """执行到期的 scheduled_take_down_at，返回处理数量。"""
    now = datetime.now(UTC)
    rows = (
        await db.scalars(
            select(Game).where(
                Game.scheduled_take_down_at.is_not(None),
                Game.scheduled_take_down_at <= now,
                Game.status == GameStatus.PUBLISHED.value,
            )
        )
    ).all()
    if not rows:
        return 0
    admin = await db.scalar(select(User).where(User.role == Role.ADMIN.value).limit(1))
    if admin is None:
        return 0
    count = 0
    for game in rows:
        gid = game.id
        await publish_services.take_down(
            db, admin, gid, reason="定时下架到期自动执行"
        )
        refreshed = await db.get(Game, gid)
        if refreshed is not None:
            refreshed.scheduled_take_down_at = None
        count += 1
    await db.commit()
    return count
