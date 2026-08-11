"""B4: play analytics tests."""

import uuid
from datetime import UTC, datetime

import fakeredis.aioredis
import httpx
from sqlalchemy import select

from app.analytics import store as analytics_store
from app.core import db
from app.models.game import Game


async def test_record_play_increments_count(
    client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    verified_client: httpx.AsyncClient,
) -> None:
    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "p", "requirement": "x"}
            )
        ).json()["data"]["game_id"]
    )
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = "play-test"
        game.published_at = datetime.now(UTC)
        game.play_count = 0
        await s.commit()

    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        await analytics_store.record_play(
            redis_client, s, slug="play-test", game_id=gid, visitor_id="1.2.3.4"
        )

    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        assert game.play_count == 1

    r = await verified_client.get(f"/api/v1/games/{gid}/analytics")
    assert r.status_code == 200
    assert r.json()["data"]["play_count"] == 1

    # 全站 rollup 也应被 record_play 顺带写入
    trend = await analytics_store.site_trend(redis_client, days=1)
    assert trend[-1]["page_views"] >= 1
    assert trend[-1]["unique_visitors"] >= 1


async def test_admin_analytics_top(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/analytics/top?limit=5")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "top_games" in data
    assert "trend" in data
    assert len(data["trend"]) == 30
    assert {"date", "page_views", "unique_visitors"} <= set(data["trend"][0])
