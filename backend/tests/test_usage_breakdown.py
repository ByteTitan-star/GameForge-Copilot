"""B3: per-game/run usage breakdown tests."""

import uuid

import fakeredis.aioredis
import httpx

from app.usage.store import record_usage


async def test_usage_breakdown_by_game(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    r = await verified_client.post(
        "/api/v1/games", json={"title": "t", "requirement": "r"}
    )
    gid = uuid.UUID(r.json()["data"]["game_id"])
    from sqlalchemy import select

    from app.core import db
    from app.models.game import Game

    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        user_id = game.owner_id

    await record_usage(
        redis_client, user_id, input_tokens=100, output_tokens=50, game_id=gid
    )

    br = await verified_client.get("/api/v1/me/usage/breakdown?scope=game")
    assert br.status_code == 200, br.text
    items = br.json()["data"]
    assert len(items) == 1
    assert items[0]["input_tokens"] == 100
    assert items[0]["estimated_usd"] >= 0


async def test_game_usage_owner(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    r = await verified_client.post(
        "/api/v1/games", json={"title": "u", "requirement": "x"}
    )
    gid = uuid.UUID(r.json()["data"]["game_id"])
    from sqlalchemy import select

    from app.core import db
    from app.models.game import Game

    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        await record_usage(
            redis_client, game.owner_id, input_tokens=10, output_tokens=5, game_id=gid
        )

    r = await verified_client.get(f"/api/v1/games/{gid}/usage")
    assert r.status_code == 200
    assert r.json()["data"]["month"]["input_tokens"] == 10
