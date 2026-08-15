"""试玩路由（根，无 /api/v1 前缀）。

docs/04：/play/{slug} 公开仅 published；/draft/{game_id}/{version} owner only。
P3：多文件 dist 子资源；/preview/{token}/... 短期 token 鉴权（§19.2）。
产物用 iframe sandbox=allow-scripts 挂载，响应加 CSP 限制脚本来源。
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.analytics import store as analytics_store
from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus
from app.hosting import preview_token, serve, store
from app.models.game import Game
from app.models.game_version import GameVersion

router = APIRouter(tags=["hosting"])


def _cache_control(prod: str) -> str:
    """dev 禁缓存（改产物/CSP 即时生效）；生产沿用 prod 策略。"""
    return "no-store" if settings.env == "development" else prod


def _artifact_headers(
    game_id: uuid.UUID, version: int, *, cache: str
) -> dict[str, str]:
    return {
        "Content-Security-Policy": serve.artifact_csp(game_id, version),
        "Cache-Control": _cache_control(cache),
    }


async def _serve_artifact(
    game_id: uuid.UUID,
    version: int,
    path: str | None,
    *,
    cache: str,
) -> Response:
    rel = serve.normalize_public_rel(path)
    return await serve.artifact_file_response(
        game_id,
        version,
        rel,
        headers=_artifact_headers(game_id, version, cache=cache),
    )


async def _owned_version(
    db: DbSession, user: CurrentUser, game_id: uuid.UUID, version: int
) -> None:
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


async def _published_game(db: DbSession, slug: str) -> Game:
    game = await db.scalar(
        select(Game).where(Game.slug == slug, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    return game


@router.get("/play/template/{template_id}")
async def play_template(template_id: str) -> Response:
    """模板 reference 产物试玩（catalog.json reference_artifact），公开。"""
    from app.core.cdn_policy import build_csp
    from app.forge.templates.loader import public_reference_path

    path = public_reference_path(template_id)
    from fastapi.responses import FileResponse

    return FileResponse(
        path,
        headers={
            "Content-Security-Policy": build_csp(),
            "Cache-Control": _cache_control("public, max-age=3600"),
        },
    )


@router.get("/play/{slug}/thumb.png")
async def play_thumb(slug: str, db: DbSession) -> Response:
    """已发布游戏封面截图，公开。不触发 PV 统计。"""
    game = await _published_game(db, slug)
    data = await store.read_bytes(game.id, game.current_version, "thumb.png")
    if data is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "封面不存在")
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": _cache_control("public, max-age=31536000, immutable")},
    )


@router.get("/play/{slug}")
async def play(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    r: RedisClient,
) -> Response:
    """已发布游戏入口，公开。非 published 一律 404。"""
    game = await _published_game(db, slug)
    visitor = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "anon"
    )
    background.add_task(
        analytics_store.record_play, r, db, slug=slug, game_id=game.id, visitor_id=visitor
    )
    return await _serve_artifact(
        game.id,
        game.current_version,
        None,
        cache="public, max-age=31536000, immutable",
    )


@router.get("/play/{slug}/{path:path}")
async def play_asset(slug: str, path: str, db: DbSession) -> Response:
    """已发布游戏 dist 子资源（assets/* 等），公开。"""
    game = await _published_game(db, slug)
    return await _serve_artifact(
        game.id,
        game.current_version,
        path,
        cache="public, max-age=31536000, immutable",
    )


@router.get("/draft/{game_id}/{version}")
async def draft(
    game_id: uuid.UUID, version: int, user: CurrentUser, db: DbSession
) -> Response:
    """草稿试玩 index.html，仅 owner。非 owner/不存在 → 404 不泄露。"""
    await _owned_version(db, user, game_id, version)
    return await _serve_artifact(
        game_id, version, None, cache="private, max-age=60"
    )


@router.get("/draft/{game_id}/{version}/{path:path}")
async def draft_asset(
    game_id: uuid.UUID,
    version: int,
    path: str,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """草稿 dist 子资源，仅 owner。"""
    await _owned_version(db, user, game_id, version)
    return await _serve_artifact(
        game_id, version, path, cache="private, max-age=60"
    )


@router.get("/preview/{token}/{game_id}/{version}")
@router.get("/preview/{token}/{game_id}/{version}/")
async def preview_index(
    token: str,
    game_id: uuid.UUID,
    version: int,
    r: RedisClient,
    db: DbSession,
) -> Response:
    """Draft 多文件 preview 入口（短期 token，§19.2）。"""
    if not await preview_token.validate_preview_token(
        r, token, game_id=game_id, version=version
    ):
        raise AppError(ErrorCode.FORBIDDEN, "预览链接无效或已过期")
    gv = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == game_id, GameVersion.version == version
        )
    )
    if gv is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "版本不存在")
    return await _serve_artifact(
        game_id, version, None, cache="private, max-age=60"
    )


@router.get("/preview/{token}/{game_id}/{version}/{path:path}")
async def preview_asset(
    token: str,
    game_id: uuid.UUID,
    version: int,
    path: str,
    r: RedisClient,
    db: DbSession,
) -> Response:
    """Draft 多文件 preview 子资源（与 index 共享 token 授权）。"""
    if not await preview_token.validate_preview_token(
        r, token, game_id=game_id, version=version
    ):
        raise AppError(ErrorCode.FORBIDDEN, "预览链接无效或已过期")
    gv = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == game_id, GameVersion.version == version
        )
    )
    if gv is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "版本不存在")
    return await _serve_artifact(
        game_id, version, path, cache="private, max-age=60"
    )
