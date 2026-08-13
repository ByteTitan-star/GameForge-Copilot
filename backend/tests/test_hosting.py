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


async def _make_version(
    gid: uuid.UUID, version: int = 1, *, write_artifact: bool = True
) -> None:
    """直接建产物 + version 行，绕过生成链。"""
    if write_artifact:
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


async def test_write_bytes_roundtrip() -> None:
    """write_bytes 写旁路产物（thumb.png）→ read_bytes 读回一致；不要求 index.html。"""
    gid = uuid.uuid4()
    png = b"\x89PNG\r\n\x1a\n fake thumbnail bytes"
    await store.write_bytes(gid, 1, "thumb.png", png)
    assert await store.read_bytes(gid, 1, "thumb.png") == png


async def test_write_bytes_rejects_traversal() -> None:
    """write_bytes 复用 _check_path，禁止 .. 路径穿越。"""
    gid = uuid.uuid4()
    with pytest.raises(AppError):
        await store.write_bytes(gid, 1, "../escape.png", b"x")


async def test_read_bytes_missing_returns_none() -> None:
    gid = uuid.uuid4()
    assert await store.read_bytes(gid, 1, "thumb.png") is None


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


async def test_download_owned_version_returns_html_attachment(
    verified_client: httpx.AsyncClient,
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.title = "browser-game"
        await s.commit()

    r = await verified_client.get(f"/api/v1/games/{gid}/versions/1/download")
    assert r.status_code == 200, r.text
    assert r.content == _HTML.encode()
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["content-disposition"] == (
        'attachment; filename="browser-game-v1.html"; '
        "filename*=UTF-8''browser-game-v1.html"
    )
    assert r.headers["cache-control"] == "private, no-store"


async def test_download_non_owner_returns_404(
    verified_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    r = await auth_client.get(f"/api/v1/games/{gid}/versions/1/download")
    assert r.status_code == 404


async def test_download_missing_version_returns_404(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    r = await verified_client.get(f"/api/v1/games/{gid}/versions/999/download")
    assert r.status_code == 404


async def test_download_missing_artifact_returns_404(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    await _make_version(gid, 1, write_artifact=False)
    r = await verified_client.get(f"/api/v1/games/{gid}/versions/1/download")
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


async def test_play_csp_uses_cdn_allowlist(verified_client: httpx.AsyncClient) -> None:
    """CSP 收敛到白名单。

    游戏可引用 three.js/tailwind/字体等公共 CDN 渲染，但不放行整个 https（防回归）。
    """
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
    # 白名单域出现在 script/style/font 来源里
    assert "cdn.jsdelivr.net" in csp
    assert "fonts.googleapis.com" in csp
    # 不再放行整个 https:（收敛前旧策略的风险点）
    assert "https:" not in csp


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
