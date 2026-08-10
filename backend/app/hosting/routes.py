"""试玩路由（根，无 /api/v1 前缀）。

docs/04：/play/{slug} 公开仅 published；/draft/{game_id}/{version} owner only。
产物用 iframe sandbox=allow-scripts 挂载，响应加 CSP 限制脚本来源。
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.analytics import store as analytics_store
from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion

router = APIRouter(tags=["hosting"])

# 产物可能引用外部 https CDN（tailwind JIT / 字体 / three.js 等），iframe sandbox=
# allow-scripts 不加 allow-same-origin（opaque origin，隔离父域 cookie/storage），故
# CSP 放宽 script/style/font 到 https：游戏脚本拿不到父域数据，但能正常加载公共 CDN 渲染。
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https:; "
    "style-src 'self' 'unsafe-inline' https:; "
    "font-src 'self' data: https:; "
    "img-src 'self' data:"
)


def _cache_control(prod: str) -> str:
    """dev 禁缓存（改产物/CSP 即时生效）；生产沿用 prod 策略。"""
    return "no-store" if settings.env == "development" else prod


@router.get("/play/{slug}")
async def play(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    r: RedisClient,
) -> FileResponse:
    """已发布游戏入口，公开。非 published 一律 404。"""
    game = await db.scalar(
        select(Game).where(Game.slug == slug, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    path = store.index_path(game.id, game.current_version)
    if path is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    visitor = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "anon"
    )
    background.add_task(
        analytics_store.record_play, r, db, slug=slug, game_id=game.id, visitor_id=visitor
    )
    return FileResponse(
        path,
        headers={
            "Content-Security-Policy": _CSP,
            "Cache-Control": _cache_control("public, max-age=31536000, immutable"),
        },
    )


@router.get("/draft/{game_id}/{version}")
async def draft(game_id: uuid.UUID, version: int, user: CurrentUser, db: DbSession) -> FileResponse:
    """草稿试玩，仅 owner。非 owner/不存在 → 404 不泄露。"""
    game = await db.scalar(
        select(Game).where(Game.id == game_id, Game.owner_id == user.id)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或不可见")
    gv = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == game_id, GameVersion.version == version
        )
    )
    if gv is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "版本不存在")
    path = store.index_path(game_id, version)
    if path is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    return FileResponse(
        path,
        headers={
            "Content-Security-Policy": _CSP,
            "Cache-Control": _cache_control("private, max-age=60"),
        },
    )
