"""公开试玩 PV/UV 统计（B4）。Redis 日粒度 + games.play_count 累计。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game


def _day() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _pv_key(slug: str) -> str:
    return f"play:pv:{slug}:{_day()}"


def _uv_key(slug: str) -> str:
    return f"play:uv:{slug}:{_day()}"


async def record_play(
    r: redis.Redis,
    db: AsyncSession,
    *,
    slug: str,
    game_id: uuid.UUID,
    visitor_id: str,
) -> None:
    """/play 成功后异步调用：PV + UV(HLL) + DB play_count。"""
    pipe = r.pipeline()
    pipe.incr(_pv_key(slug))
    pipe.pfadd(_uv_key(slug), visitor_id)
    pipe.expire(_pv_key(slug), 40 * 86400)
    pipe.expire(_uv_key(slug), 40 * 86400)
    await pipe.execute()
    game = await db.get(Game, game_id)
    if game is not None:
        game.play_count = int(game.play_count or 0) + 1
        await db.commit()


async def game_analytics(r: redis.Redis, slug: str, *, days: int = 30) -> dict[str, int]:
    """近 N 日 PV/UV 汇总（按 slug）。"""
    pv = 0
    uv = 0
    now = datetime.now(UTC)
    for i in range(days):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        pv += int(await r.get(f"play:pv:{slug}:{d}") or 0)
        uv += int(await r.pfcount(f"play:uv:{slug}:{d}") or 0)
    return {"pv_30d": pv, "uv_30d": uv}
