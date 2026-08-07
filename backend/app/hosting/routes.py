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
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion

router = APIRouter(tags=["hosting"])

# 产物是 LLM 生成的单文件 HTML（内联 <script>），iframe sandbox=allow-scripts 不加
# allow-same-origin（隔离 origin/cookie），故允许 inline 不引入同源风险。
_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:"
)


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
            "Cache-Control": "public, max-age=31536000, immutable",
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
            "Cache-Control": "private, max-age=60",
        },
    )
