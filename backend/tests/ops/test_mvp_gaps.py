"""docs/01 MVP 缺口：重命名 / pause·cancel / 审计 / admin games / 站内通知。"""

import uuid

import httpx
from app.core import db
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion
from sqlalchemy import select


async def test_rename_draft(verified_client: httpx.AsyncClient) -> None:
    r = await verified_client.post("/api/v1/games", json={"title": "旧名", "requirement": "r"})
    gid = r.json()["data"]["game_id"]
    r = await verified_client.patch(f"/api/v1/games/{gid}", json={"title": "新名"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["title"] == "新名"


async def test_pause_cancel_run(verified_client: httpx.AsyncClient, redis_client) -> None:
    g = await verified_client.post("/api/v1/games", json={"title": "a", "requirement": "r"})
    gid = g.json()["data"]["game_id"]
    run = await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "go"})
    rid = run.json()["data"]["run_id"]

    paused = await verified_client.post(f"/api/v1/runs/{rid}/pause")
    assert paused.status_code == 200
    assert paused.json()["data"]["status"] == "paused"

    cancelled = await verified_client.post(f"/api/v1/runs/{rid}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "failed"


async def test_admin_audit_and_games(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    g = await verified_client.post("/api/v1/games", json={"title": "PubGame", "requirement": "r"})
    gid = uuid.UUID(g.json()["data"]["game_id"])
    await store.write_artifact(gid, 1, {"index.html": "<html></html>"})
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.current_version = 1
        s.add(
            GameVersion(game_id=gid, version=1, artifact_path=f"{gid}/1/index.html", design_doc={})
        )
        await s.commit()
    sub = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    pr = sub.json()["data"]["publish_request_id"]
    await admin_client.post(f"/api/v1/publish/{pr}/approve")

    games = await admin_client.get("/api/v1/admin/games")
    assert games.status_code == 200
    assert any(x["game_id"] == str(gid) for x in games.json()["data"])

    logs = await admin_client.get("/api/v1/admin/audit-logs")
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
    assert any(x["action"] == "approve" for x in logs.json()["data"])


async def test_notifications_inbox(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    g = await verified_client.post("/api/v1/games", json={"title": "N", "requirement": "r"})
    gid = uuid.UUID(g.json()["data"]["game_id"])
    await store.write_artifact(gid, 1, {"index.html": "<html></html>"})
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.current_version = 1
        s.add(
            GameVersion(game_id=gid, version=1, artifact_path=f"{gid}/1/index.html", design_doc={})
        )
        await s.commit()
    sub = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    await admin_client.post(f"/api/v1/publish/{sub.json()['data']['publish_request_id']}/approve")

    inbox = await verified_client.get("/api/v1/me/notifications")
    assert inbox.status_code == 200
    assert len(inbox.json()["data"]) >= 1
    nid = inbox.json()["data"][0]["id"]
    read = await verified_client.post(f"/api/v1/me/notifications/{nid}/read")
    assert read.status_code == 200
    assert read.json()["data"]["read"] is True
