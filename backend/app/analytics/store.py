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


# 全站聚合 rollup（独立命名空间，避免与某个真实 slug 冲突）
def _site_pv_key(day: str | None = None) -> str:
    return f"analytics:site:pv:{day or _day()}"


def _site_uv_key(day: str | None = None) -> str:
    return f"analytics:site:uv:{day or _day()}"


async def record_play(
    r: redis.Redis,
    db: AsyncSession,
    *,
    slug: str,
    game_id: uuid.UUID,
    visitor_id: str,
) -> None:
    """/play 成功后异步调用：per-slug PV/UV + 全站 rollup PV/UV + DB play_count。"""
    pipe = r.pipeline()
    pipe.incr(_pv_key(slug))
    pipe.pfadd(_uv_key(slug), visitor_id)
    pipe.expire(_pv_key(slug), 40 * 86400)
    pipe.expire(_uv_key(slug), 40 * 86400)
    # 全站 rollup：跨所有游戏聚合，供 admin 访问分析趋势
    pipe.incr(_site_pv_key())
    pipe.pfadd(_site_uv_key(), visitor_id)
    pipe.expire(_site_pv_key(), 40 * 86400)
    pipe.expire(_site_uv_key(), 40 * 86400)
    await pipe.execute()
    game = await db.get(Game, game_id)
    if game is not None:
        game.play_count = int(game.play_count or 0) + 1
        await db.commit()


async def site_trend(r: redis.Redis, *, days: int = 30) -> list[dict]:
    """全站近 N 日 PV/UV 趋势（最早一天到今天，正序）。供 admin 访问分析。"""
    out: list[dict] = []
    now = datetime.now(UTC)
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        pv = int(await r.get(_site_pv_key(d)) or 0)
        uv = int(await r.pfcount(_site_uv_key(d)) or 0)
        out.append({"date": d, "page_views": pv, "unique_visitors": uv})
    return out


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
