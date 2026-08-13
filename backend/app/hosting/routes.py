"""试玩路由（根，无 /api/v1 前缀）。

docs/04：/play/{slug} 公开仅 published；/draft/{game_id}/{version} owner only。
产物用 iframe sandbox=allow-scripts 挂载，响应加 CSP 限制脚本来源。
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from app.analytics import store as analytics_store
from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.cdn_policy import build_csp
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion

router = APIRouter(tags=["hosting"])

# 产物引用公共 CDN（three.js / tailwind / 字体等）渲染；CSP 收敛到 app.core.cdn_policy
# 白名单，不再放行整个 https:，避免任意外站脚本跑进 iframe。iframe sandbox=allow-scripts
# 不加 allow-same-origin（opaque origin，隔离父域 cookie/storage），游戏脚本拿不到父域数据。
_CSP = build_csp()


def _cache_control(prod: str) -> str:
    """dev 禁缓存（改产物/CSP 即时生效）；生产沿用 prod 策略。"""
    return "no-store" if settings.env == "development" else prod


async def _html_response(
    game_id: uuid.UUID, version: int, headers: dict[str, str]
) -> Response:
    """本地文件优先；无本地缓存时从对象存储读取。"""
    path = store.index_path(game_id, version)
    if path is not None:
        return FileResponse(path, headers=headers)
    data = await store.read_bytes(game_id, version, "index.html")
    if data is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    return Response(content=data, media_type="text/html; charset=utf-8", headers=headers)


@router.get("/play/{slug}")
async def play(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    r: RedisClient,
) -> Response:
    """已发布游戏入口，公开。非 published 一律 404。"""
    game = await db.scalar(
        select(Game).where(Game.slug == slug, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    visitor = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "anon"
    )
    background.add_task(
        analytics_store.record_play, r, db, slug=slug, game_id=game.id, visitor_id=visitor
    )
    return await _html_response(
        game.id,
        game.current_version,
        {
            "Content-Security-Policy": _CSP,
            "Cache-Control": _cache_control("public, max-age=31536000, immutable"),
        },
    )


@router.get("/draft/{game_id}/{version}")
async def draft(game_id: uuid.UUID, version: int, user: CurrentUser, db: DbSession) -> Response:
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
    return await _html_response(
        game_id,
        version,
        {
            "Content-Security-Policy": _CSP,
            "Cache-Control": _cache_control("private, max-age=60"),
        },
    )


def _png_response(data: bytes | None, prod_cache: str) -> Response:
    """封面 png：读不到时 404（让前端 <img onError> 触发渐变降级），不返回占位图。"""
    if data is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "封面不存在")
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": _cache_control(prod_cache)},
    )


@router.get("/play/{slug}/thumb.png")
async def play_thumb(slug: str, db: DbSession) -> Response:
    """已发布游戏封面截图，公开。不触发 PV 统计。"""
    game = await db.scalar(
        select(Game).where(Game.slug == slug, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    data = await store.read_bytes(game.id, game.current_version, "thumb.png")
    return _png_response(data, "public, max-age=31536000, immutable")
