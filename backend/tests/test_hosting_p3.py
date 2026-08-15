"""P3 多文件 Hosting + preview token 路由测试。"""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.core import db
from app.hosting import preview_token, store
from app.main import app
from app.models.game import Game
from app.models.game_version import GameVersion
from tests.conftest import _sent

_HTML = (
    '<!doctype html><html><head>'
    '<script src="./assets/app.js"></script></head><body></body></html>'
)
_JS = "console.log('ok')"
_GAME = {"title": "多文件", "requirement": "test"}


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=_GAME)
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_project_version(gid: uuid.UUID, version: int = 1) -> None:
    await store.write_version_layers(
        gid,
        version,
        source={"src/main.ts": b"x"},
        build_snapshot={"package.json": b"{}"},
        dist={"index.html": _HTML.encode(), "assets/app.js": _JS.encode()},
    )
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.current_version = version
        s.add(
            GameVersion(
                game_id=gid,
                version=version,
                artifact_path=f"{gid}/{version}/index.html",
                design_doc={},
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_draft_serves_asset(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    r = await verified_client.get(f"/draft/{gid}/1/assets/app.js")
    assert r.status_code == 200, r.text
    assert r.text == _JS


@pytest.mark.asyncio
async def test_draft_blocks_source_path(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    r = await verified_client.get(f"/draft/{gid}/1/source/src/main.ts")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_play_published_serves_assets(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = "multi-file-game"
        await s.commit()
    r = await verified_client.get("/play/multi-file-game/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


@pytest.mark.asyncio
async def test_project_artifact_uses_strict_csp(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    r = await verified_client.get(f"/draft/{gid}/1")
    csp = r.headers.get("content-security-policy", "")
    assert "connect-src 'none'" in csp
    assert "cdn.jsdelivr.net" not in csp


@pytest.mark.asyncio
async def test_preview_token_serves_index_and_assets(
    verified_client: httpx.AsyncClient, redis_client
) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        owner_id = game.owner_id
    token = await preview_token.mint_preview_token(
        redis_client, game_id=gid, version=1, owner_id=owner_id
    )
    r = await verified_client.get(f"/preview/{token}/{gid}/1/")
    assert r.status_code == 200, r.text
    assert "assets/app.js" in r.text
    r2 = await verified_client.get(f"/preview/{token}/{gid}/1/assets/app.js")
    assert r2.status_code == 200
    assert r2.text == _JS


@pytest.mark.asyncio
async def test_preview_invalid_token_403(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    r = await verified_client.get(f"/preview/bad-token/{gid}/1/")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_preview_token_api(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    r = await verified_client.post(f"/api/v1/games/{gid}/versions/1/preview-token")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["preview_url"].startswith("/preview/")
    assert data["expires_in_s"] > 0
    r2 = await verified_client.get(data["preview_url"])
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_preview_expired_token_http_403(
    verified_client: httpx.AsyncClient, redis_client
) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        owner_id = game.owner_id
    token = await preview_token.mint_preview_token(
        redis_client, game_id=gid, version=1, owner_id=owner_id
    )
    await redis_client.delete(f"preview:{token}")
    r = await verified_client.get(f"/preview/{token}/{gid}/1/")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_preview_token_non_owner_404(
    verified_client: httpx.AsyncClient,
) -> None:
    gid = await _make_game(verified_client)
    await _make_project_version(gid, 1)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as other:
        await other.post(
            "/api/v1/auth/register",
            json={"email": "other@v.com", "password": "password123"},
        )
        token = _sent["verify:other@v.com"]
        await other.post(
            "/api/v1/auth/verify-email",
            json={"email": "other@v.com", "code": token},
        )
        login = await other.post(
            "/api/v1/auth/login",
            json={"email": "other@v.com", "password": "password123"},
        )
        other.headers["Authorization"] = (
            f"Bearer {login.json()['data']['access_token']}"
        )
        r = await other.post(f"/api/v1/games/{gid}/versions/1/preview-token")
        assert r.status_code == 404
