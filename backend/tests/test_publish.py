"""M7 发布审批：submit/queue/approve/reject/take_down + 状态机 + admin 守卫 + slug。"""

import uuid

import httpx
from sqlalchemy import select

from app.core import db
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion

_GAME = {"title": "贪吃蛇", "requirement": "方向键"}
_HTML = "<html><body>game</body></html>"


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=_GAME)
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_version(gid: uuid.UUID, version: int = 1) -> None:
    await store.write_artifact(gid, version, {"index.html": _HTML})
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.current_version = version
        s.add(
            GameVersion(
                game_id=gid, version=version,
                artifact_path=f"{gid}/{version}/index.html", design_doc={},
            )
        )
        await s.commit()


async def test_submit_and_approve_flow(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)

    # owner submit
    r = await verified_client.post(
        f"/api/v1/games/{gid}/publish/submit", json={"version": 1}
    )
    assert r.status_code == 200, r.text
    pr_id = r.json()["data"]["publish_request_id"]
    assert r.json()["data"]["status"] == "submitted"

    # admin queue
    r = await admin_client.get("/api/v1/publish/queue")
    assert r.status_code == 200
    assert any(p["publish_request_id"] == pr_id for p in r.json()["data"])

    # admin approve → published + slug
    r = await admin_client.post(f"/api/v1/publish/{pr_id}/approve")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "approved"
    assert d["game"]["status"] == "published"
    slug = d["game"]["slug"]
    assert slug

    # /play/{slug} 公开可访问
    r = await admin_client.get(f"/play/{slug}")
    assert r.status_code == 200 and "game" in r.text


async def test_reject_flow(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    r = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    pr_id = r.json()["data"]["publish_request_id"]

    r = await admin_client.post(
        f"/api/v1/publish/{pr_id}/reject", json={"reason": "玩法问题"}
    )
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "rejected"
    assert d["game"]["status"] == "rejected"

    # rejected 后可重新 submit（状态机）
    r = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    assert r.status_code == 200


async def test_take_down(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    r = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    pr_id = r.json()["data"]["publish_request_id"]
    await admin_client.post(f"/api/v1/publish/{pr_id}/approve")

    r = await admin_client.post(f"/api/v1/games/{gid}/take-down", json={"reason": "违规"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "taken_down"


async def test_submit_invalid_state_409(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    r = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    pr_id = r.json()["data"]["publish_request_id"]
    await admin_client.post(f"/api/v1/publish/{pr_id}/approve")
    # published 再 submit → 409
    r = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    assert r.status_code == 409


async def test_take_down_non_published_409(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    # draft 不可下架 → 409
    r = await admin_client.post(f"/api/v1/games/{gid}/take-down", json={"reason": "x"})
    assert r.status_code == 409


async def test_admin_guards(auth_client: httpx.AsyncClient) -> None:
    """普通用户访问 admin 端点 → 403。"""
    r = await auth_client.get("/api/v1/publish/queue")
    assert r.status_code == 403
    r = await auth_client.post("/api/v1/publish/00000000-0000-4000-8000-000000000001/approve")
    assert r.status_code == 403


async def test_submit_non_owner_404(
    verified_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    # auth_client 是未验证的另一用户；submit 非 owner → 404
    r = await auth_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    assert r.status_code == 404
