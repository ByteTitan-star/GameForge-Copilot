"""封面截图路由：/play/{slug}/thumb.png 公开读取 published 游戏封面。

draft 封面路由已移除（<img> 无法带 owner Bearer，会 401）；草稿卡片回退渐变。
"""

import uuid

import httpx
from app.core import db
from app.hosting import store
from app.models.game import Game
from sqlalchemy import select

_PNG = b"\x89PNG\r\n\x1a\n fake thumbnail"

_GAME = {"title": "封面蛇", "requirement": "方向键"}


async def _make_published_game(
    client: httpx.AsyncClient, *, slug: str, with_thumb: bool
) -> uuid.UUID:
    """建一个 published 游戏并可选写入 thumb.png，返回 game_id。"""
    gid = uuid.UUID((await client.post("/api/v1/games", json=_GAME)).json()["data"]["game_id"])
    await store.write_artifact(gid, 1, {"index.html": "<!doctype html><body>stub</body>"})
    if with_thumb:
        await store.write_bytes(gid, 1, "thumb.png", _PNG)
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.status = "published"
        game.slug = slug
        game.current_version = 1
        game.cover_path = "thumb.png" if with_thumb else None
        await s.commit()
    return gid


async def test_play_thumb_returns_png_for_published(
    verified_client: httpx.AsyncClient,
) -> None:
    """已发布游戏 + 有 thumb.png → 200 image/png，内容为截图字节。"""
    await _make_published_game(verified_client, slug="thumb-ok", with_thumb=True)
    r = await verified_client.get("/play/thumb-ok/thumb.png")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert r.content == _PNG


async def test_play_thumb_404_when_not_published(verified_client: httpx.AsyncClient) -> None:
    """slug 存在但游戏未发布（draft）→ 404，不泄露封面。"""
    await _make_published_game(verified_client, slug="thumb-draft", with_thumb=True)
    # 改回 draft
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.slug == "thumb-draft"))).first()
        assert game is not None
        game.status = "draft"
        await s.commit()
    r = await verified_client.get("/play/thumb-draft/thumb.png")
    assert r.status_code == 404


async def test_play_thumb_404_when_unknown_slug(verified_client: httpx.AsyncClient) -> None:
    """slug 不存在 → 404。"""
    r = await verified_client.get("/play/no-such-game/thumb.png")
    assert r.status_code == 404


async def test_play_thumb_404_when_no_file(verified_client: httpx.AsyncClient) -> None:
    """已发布但磁盘无 thumb.png（截图失败降级）→ 404，前端 onError 回退渐变。"""
    # with_thumb=False：published 但无产物文件
    await _make_published_game(verified_client, slug="thumb-missing", with_thumb=False)
    r = await verified_client.get("/play/thumb-missing/thumb.png")
    assert r.status_code == 404
