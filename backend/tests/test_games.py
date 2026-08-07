"""M4 游戏 CRUD：创建/列表/详情/删除 + 可见性 + 未验证 403。"""

import uuid

import httpx
from sqlalchemy import select

from app.models.game import Game

_BODY = {"title": "贪吃蛇", "requirement": "方向键控制，计分"}


async def _create(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=_BODY)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["game_id"])


async def test_create_requires_verified(auth_client: httpx.AsyncClient) -> None:
    r = await auth_client.post("/api/v1/games", json=_BODY)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


async def test_crud(verified_client: httpx.AsyncClient) -> None:
    gid = await _create(verified_client)
    # 列表含此游戏
    r = await verified_client.get("/api/v1/games")
    assert r.status_code == 200
    assert any(g["game_id"] == str(gid) for g in r.json()["data"])
    # 详情
    r = await verified_client.get(f"/api/v1/games/{gid}")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "draft"
    assert d["current_version"] == 0
    assert d["versions"] == []
    # 删除草稿
    r = await verified_client.delete(f"/api/v1/games/{gid}")
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True
    # 再取详情 → 404
    r = await verified_client.get(f"/api/v1/games/{gid}")
    assert r.status_code == 404


async def test_non_owner_404(
    verified_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    """admin/他人不可见草稿（docs/06）；非 owner → 404 不泄露。"""
    gid = await _create(verified_client)
    r = await auth_client.get(f"/api/v1/games/{gid}")
    assert r.status_code == 404


async def test_delete_non_deletable_409(verified_client: httpx.AsyncClient) -> None:
    """非 draft/rejected/taken_down 不可删 → 409。"""
    from app.core import db

    gid = await _create(verified_client)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        await s.commit()
    r = await verified_client.delete(f"/api/v1/games/{gid}")
    assert r.status_code == 409
