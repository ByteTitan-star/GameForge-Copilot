"""M5 托管：store 写读+超限 / /draft owner+可见性 / /play published+404。

hosting 路由测试不依赖生成链（直接建 version+产物）；生成链在 test_runs 覆盖。
"""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.core import db
from app.core.errors import AppError
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion

_HTML = "<!doctype html><html><body><h1>stub game</h1></body></html>"
_GAME = {"title": "贪吃蛇", "requirement": "方向键"}


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=_GAME)
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_version(gid: uuid.UUID, version: int = 1) -> None:
    """直接建产物 + version 行，绕过生成链。"""
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


async def test_store_write_and_read() -> None:
    gid = uuid.uuid4()
    p = await store.write_artifact(gid, 1, {"index.html": _HTML})
    assert p.exists()
    assert store.index_path(gid, 1) == p


async def test_store_size_limit() -> None:
    gid = uuid.uuid4()
    big = {"index.html": "x" * (60 * 1024 * 1024)}
    with pytest.raises(AppError):
        await store.write_artifact(gid, 1, big)


async def test_draft_owner_200(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    r = await verified_client.get(f"/draft/{gid}/1")
    assert r.status_code == 200, r.text
    assert "stub game" in r.text


async def test_draft_non_owner_404(
    verified_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    r = await auth_client.get(f"/draft/{gid}/1")
    assert r.status_code == 404


async def test_draft_version_not_found(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    r = await verified_client.get(f"/draft/{gid}/999")
    assert r.status_code == 404


async def test_play_non_published_404(verified_client: httpx.AsyncClient) -> None:
    r = await verified_client.get("/play/no-such-slug")
    assert r.status_code == 404


async def test_play_published_200(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = "snake-xxx"
        await s.commit()
    r = await verified_client.get("/play/snake-xxx")
    assert r.status_code == 200, r.text
    assert "stub game" in r.text


async def test_play_csp_allows_https_cdn(verified_client: httpx.AsyncClient) -> None:
    """CSP 放宽到 https：游戏可引用 tailwind/字体/库等公共 CDN 渲染（防回归）。"""
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = "csp-probe"
        await s.commit()
    r = await verified_client.get("/play/csp-probe")
    csp = r.headers.get("content-security-policy", "")
    assert "script-src 'self' 'unsafe-inline' https:" in csp
    assert "style-src 'self' 'unsafe-inline' https:" in csp
    assert "font-src 'self' data: https:" in csp


async def test_play_dev_disables_cache(verified_client: httpx.AsyncClient) -> None:
    """dev 环境 /play 禁缓存，改产物/CSP 后刷新即生效（防回归）。"""
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = "cache-probe"
        await s.commit()
    r = await verified_client.get("/play/cache-probe")
    assert "no-store" in r.headers.get("cache-control", "")
