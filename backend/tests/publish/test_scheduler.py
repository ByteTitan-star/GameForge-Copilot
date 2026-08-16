"""B8: scheduled take-down / republish scan."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.core import db
from app.models.game import Game
from app.scheduler.services import scan_scheduled


async def test_scan_scheduled_take_down(
    admin_client: httpx.AsyncClient, verified_client: httpx.AsyncClient
) -> None:
    gid = uuid.UUID(
        (
            await verified_client.post("/api/v1/games", json={"title": "sched", "requirement": "x"})
        ).json()["data"]["game_id"]
    )

    due = datetime.now(UTC) - timedelta(minutes=1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = "sched-game"
        game.scheduled_take_down_at = due
        await s.commit()

    async with db.SessionLocal() as s:
        n = await scan_scheduled(s)
        assert n == 1
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        assert game.status == "taken_down"
        assert game.scheduled_take_down_at is None

    r = await admin_client.patch(
        f"/api/v1/admin/games/{gid}/schedule",
        json={"scheduled_take_down_at": None, "scheduled_publish_at": None},
    )
    assert r.status_code == 200


async def test_scan_scheduled_republish(
    admin_client: httpx.AsyncClient, verified_client: httpx.AsyncClient
) -> None:
    """到期 scheduled_publish_at：TAKEN_DOWN → PUBLISHED。"""
    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "resched", "requirement": "x"}
            )
        ).json()["data"]["game_id"]
    )

    due = datetime.now(UTC) - timedelta(minutes=1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "taken_down"
        game.slug = "resched-game"
        game.scheduled_publish_at = due
        await s.commit()

    async with db.SessionLocal() as s:
        n = await scan_scheduled(s)
        assert n == 1
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        assert game.status == "published"
        assert game.scheduled_publish_at is None
