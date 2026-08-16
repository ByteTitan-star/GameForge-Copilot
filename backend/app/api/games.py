"""游戏端点（M4 真实逻辑）：CRUD + versions + 可见性（owner 过滤）。"""

import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse, ErrorResponse, PaginatedData
from app.enums import GameStatus, PublishStatus, ReactionType
from app.games import official as official_svc
from app.games import services
from app.hosting import preview_token as preview_token_svc
from app.hosting import store as hosting_store
from app.hosting.backend import ArtifactFileMeta
from app.models.game import Game
from app.models.game_version import GameVersion
from app.profile import services as profile_services
from app.publish import services as publish_services
from app.reactions import services as reaction_services
from app.schemas.game import (
    ArtifactFileItem,
    GameBatchDeleteReq,
    GameBatchDeleteResp,
    GameCreate,
    GameDeleteResp,
    GameDetailResp,
    GameListItem,
    GamePatch,
    GameResp,
    PreviewTokenResp,
    VersionItem,
)
from app.schemas.publish import PublishSubmitResp
from app.schemas.reactions import (
    CreatorBrief,
    PublicGameMeta,
    ReactionStateResp,
    ReactionToggleResp,
)

router = APIRouter(prefix="/games", tags=["games"])

ERR_404 = {404: {"model": ErrorResponse, "description": "游戏不存在或不可见"}}
ERR_403 = {403: {"model": ErrorResponse, "description": "邮箱未验证"}}
ERR_409 = {409: {"model": ErrorResponse, "description": "状态冲突"}}


def _to_resp(game: Game) -> GameResp:
    return GameResp(
        game_id=game.id,
        owner_id=game.owner_id,
        title=game.title,
        status=GameStatus(game.status),
        current_version=game.current_version,
        created_at=game.created_at,
    )


def _to_item(game: Game) -> GameListItem:
    # 仅已发布游戏拼封面：走公开 /play/{slug}/thumb.png，<img> 可直连。
    # 草稿走 /draft/{id}/{ver}/thumb.png 需 owner 鉴权，<img> 带不了 Bearer → 不拼，
    # 草稿卡片回退渐变（点进预览即可见实际画面）。
    cover_url = None
    if game.cover_path and game.status == GameStatus.PUBLISHED.value and game.slug:
        cover_url = f"/play/{game.slug}/thumb.png"
    return GameListItem(
        game_id=game.id,
        title=game.title,
        status=GameStatus(game.status),
        current_version=game.current_version,
        slug=game.slug,
        cover_url=cover_url,
        updated_at=game.updated_at,
    )


def _to_version(v: GameVersion) -> VersionItem:
    return VersionItem(
        version=v.version,
        artifact_path=v.artifact_path,
        thumbnail_path=v.thumbnail_path,
        created_at=v.created_at,
    )


def _download_headers(title: str, version: int) -> dict[str, str]:
    safe_title = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", title).strip(" .-") or "game"
    filename = f"{safe_title}-v{version}.html"
    fallback = filename if filename.isascii() else f"game-v{version}.html"
    return {
        "Content-Disposition": (
            f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
        ),
        "Cache-Control": "private, no-store",
    }


async def _public_item(db: DbSession, game: Game, locale: str | None = None) -> PublicGameMeta:
    handle, display_name = await profile_services.get_owner_brief(db, game.owner_id)
    like_count, favorite_count = await reaction_services.reaction_counts(db, game.id)
    title = official_svc.localized_game_title(game, locale)
    return PublicGameMeta(
        game_id=game.id,
        title=title,
        slug=game.slug or "",
        cover_url=(f"/play/{game.slug}/thumb.png" if game.cover_path and game.slug else None),
        published_at=game.published_at,
        play_count=game.play_count,
        featured=game.featured_rank is not None,
        like_count=like_count,
        favorite_count=favorite_count,
        creator=CreatorBrief(handle=handle, display_name=display_name),
    )


@router.post("", response_model=ApiResponse[GameResp], status_code=201, responses=ERR_403)
async def create_game(
    req: GameCreate, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[GameResp]:
    return ApiResponse(data=_to_resp(await services.create_game(db, user, req, r)))


@router.get("/public", response_model=PaginatedData[PublicGameMeta])
async def list_public_games(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("updated_at", pattern="^(updated_at|play_count)$"),
    locale: str | None = Query(None, description="zh | en，官方样例标题随 locale 切换"),
) -> PaginatedData[PublicGameMeta]:
    """公开已发布游戏发现页（无需登录，无 owner PII）。"""
    rows, total = await services.list_public_games(db, page, size, sort)
    data = [await _public_item(db, g, locale) for g in rows]
    return PaginatedData(data=data, total=total, page=page, size=size)


@router.get("/featured", response_model=PaginatedData[PublicGameMeta])
async def list_featured_games(
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    locale: str | None = Query(None, description="zh | en，官方样例标题随 locale 切换"),
) -> PaginatedData[PublicGameMeta]:
    """本周精选（Batch C · R7）。"""
    rows, total = await services.list_featured_games(db, page, size)
    data = [await _public_item(db, g, locale) for g in rows]
    return PaginatedData(data=data, total=total, page=page, size=size)


@router.get("/public/{slug}", response_model=ApiResponse[PublicGameMeta], responses=ERR_404)
async def get_public_game_meta(
    slug: str,
    db: DbSession,
    locale: str | None = Query(None, description="zh | en，官方样例标题随 locale 切换"),
) -> ApiResponse[PublicGameMeta]:
    game = await services.get_public_game_by_slug(db, slug)
    return ApiResponse(data=await _public_item(db, game, locale))


@router.post(
    "/fork/{slug}",
    response_model=ApiResponse[GameResp],
    status_code=201,
    responses={**ERR_403, **ERR_404, **ERR_409},
)
async def fork_official_game(
    slug: str, user: CurrentUser, db: DbSession
) -> ApiResponse[GameResp]:
    """Fork 官方预置游戏为当前用户 draft（Batch A · R1）。"""
    return ApiResponse(data=_to_resp(await official_svc.fork_official_game(db, user, slug)))


@router.get("", response_model=PaginatedData[GameListItem])
async def list_games(
    user: CurrentUser,
    db: DbSession,
    status: GameStatus | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[GameListItem]:
    rows, total = await services.list_games(db, user, status, page, size)
    return PaginatedData(data=[_to_item(g) for g in rows], total=total, page=page, size=size)


@router.post(
    "/batch-delete",
    response_model=ApiResponse[GameBatchDeleteResp],
    responses={**ERR_404, **ERR_409},
)
async def batch_delete_games(
    req: GameBatchDeleteReq, user: CurrentUser, db: DbSession
) -> ApiResponse[GameBatchDeleteResp]:
    """批量删除：已发布/审核中的会被状态规则挡下并计入 failed。"""
    deleted, failed = await services.delete_games(db, user, req.game_ids)
    return ApiResponse(
        data=GameBatchDeleteResp(
            deleted=deleted,
            failed=[{"game_id": gid, "reason": reason} for gid, reason in failed],
        )
    )


@router.patch("/{game_id}", response_model=ApiResponse[GameResp], responses={**ERR_404, **ERR_409})
async def patch_game(
    game_id: UUID, req: GamePatch, user: CurrentUser, db: DbSession
) -> ApiResponse[GameResp]:
    """草稿重命名（docs/01 MVP）。"""
    return ApiResponse(data=_to_resp(await services.patch_game(db, user, game_id, req)))


@router.get("/{game_id}", response_model=ApiResponse[GameDetailResp], responses=ERR_404)
async def get_game(game_id: UUID, user: CurrentUser, db: DbSession) -> ApiResponse[GameDetailResp]:
    game, versions = await services.get_game_detail(db, user, game_id)
    return ApiResponse(
        data=GameDetailResp(
            game_id=game.id,
            owner_id=game.owner_id,
            title=game.title,
            status=GameStatus(game.status),
            current_version=game.current_version,
            slug=game.slug,
            versions=[_to_version(v) for v in versions],
            created_at=game.created_at,
            updated_at=game.updated_at,
        )
    )


@router.delete(
    "/{game_id}",
    response_model=ApiResponse[GameDeleteResp],
    responses={**ERR_404, **ERR_409},
)
async def delete_game(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[GameDeleteResp]:
    game = await services.delete_game(db, user, game_id)
    return ApiResponse(data=GameDeleteResp(game_id=game.id))


@router.post(
    "/{game_id}/unpublish",
    response_model=ApiResponse[GameResp],
    responses={**ERR_404, **ERR_409},
)
async def unpublish_game(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[GameResp]:
    """owner 自助下架已发布游戏（published → taken_down）。

    与 admin 的 take-down 区分：owner 自助操作，无需原因。
    """
    return ApiResponse(data=_to_resp(await services.unpublish_own_game(db, user, game_id)))


@router.post(
    "/{game_id}/publish/withdraw",
    response_model=ApiResponse[PublishSubmitResp],
    responses={**ERR_404, **ERR_409},
)
async def withdraw_publish(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[PublishSubmitResp]:
    """owner 撤回待审核的发布申请（submitted/reviewing → withdrawn，游戏回 draft）。"""
    pr = await publish_services.withdraw_by_game(db, user, game_id)
    return ApiResponse(
        data=PublishSubmitResp(
            publish_request_id=pr.id,
            status=PublishStatus(pr.status),
            game_id=pr.game_id,
            version=pr.version,
        )
    )


@router.get(
    "/{game_id}/versions",
    response_model=ApiResponse[list[VersionItem]],
    responses=ERR_404,
)
async def list_versions(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[list[VersionItem]]:
    rows = await services.list_versions(db, user, game_id)
    return ApiResponse(data=[_to_version(v) for v in rows])


@router.get(
    "/{game_id}/versions/{version}/download",
    response_class=Response,
    responses={
        200: {
            "description": "游戏 HTML 版本下载",
            "content": {"text/html": {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {
                    "description": "附件文件名",
                    "schema": {"type": "string"},
                }
            },
        },
        **ERR_404,
    },
)
async def download_version(
    game_id: UUID, version: int, user: CurrentUser, db: DbSession
) -> Response:
    """Download an owned version as a standalone HTML file."""
    game, _ = await services.get_owned_version(db, user, game_id, version)
    content = await hosting_store.read_bytes(game_id, version, "index.html")
    if content is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    return Response(
        content=content,
        media_type="text/html",
        headers=_download_headers(game.title, version),
    )


def _artifact_file_items(
    metas: list[ArtifactFileMeta],
) -> list[ArtifactFileItem]:
    return [ArtifactFileItem(path=m.path, size=m.size, mime=m.mime) for m in metas]


@router.get(
    "/{game_id}/versions/{version}/files",
    response_model=ApiResponse[list[ArtifactFileItem]],
    responses=ERR_404,
)
async def list_version_files(
    game_id: UUID, version: int, user: CurrentUser, db: DbSession
) -> ApiResponse[list[ArtifactFileItem]]:
    """列出某版本产物下的全部文件（代码预览文件树，owner only）。

    空产物（版本未生成/已清理）返回 data: []，不当作 404。
    """
    await services.get_owned_version(db, user, game_id, version)
    metas = await hosting_store.list_files(game_id, version)
    return ApiResponse(data=_artifact_file_items(metas))


@router.post(
    "/{game_id}/versions/{version}/preview-token",
    response_model=ApiResponse[PreviewTokenResp],
    responses=ERR_404,
)
async def create_preview_token(
    game_id: UUID,
    version: int,
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[PreviewTokenResp]:
    """签发 draft 多文件 preview token（owner only，§19.2）。"""
    game, _ = await services.get_owned_version(db, user, game_id, version)
    token = await preview_token_svc.mint_preview_token(
        r,
        game_id=game_id,
        version=version,
        owner_id=game.owner_id,
    )
    return ApiResponse(
        data=PreviewTokenResp(
            preview_url=preview_token_svc.preview_url_path(token, game_id, version),
            expires_in_s=settings.draft_url_ttl_s,
        )
    )


@router.get(
    "/{game_id}/versions/{version}/files/{file_path:path}",
    response_class=Response,
    responses={
        200: {
            "description": "产物文件原始内容",
            "content": {"text/plain": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ERR_404,
    },
)
async def fetch_version_file(
    game_id: UUID,
    version: int,
    file_path: str,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """读取某版本产物下单个文件的原始字节（代码预览内容，owner only）。

    file_path 由 FastAPI :path 转换器吃下斜杠；read_bytes 已做防穿越校验。
    文件不存在/越界一律 GAME_NOT_FOUND，不泄漏存在性。
    """
    await services.get_owned_version(db, user, game_id, version)
    try:
        content = await hosting_store.read_bytes(game_id, version, file_path)
    except AppError as exc:  # 越界路径（SANDBOX_FAILED）→ 归类为 404，与"不存在"一致不泄漏
        if exc.code == ErrorCode.SANDBOX_FAILED:
            raise AppError(ErrorCode.GAME_NOT_FOUND, "产物文件不存在") from exc
        raise
    if content is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物文件不存在")
    return Response(content=content, media_type="text/plain; charset=utf-8")


@router.post(
    "/{game_id}/versions/{version}/activate",
    response_model=ApiResponse[GameResp],
    responses={**ERR_404, **ERR_409},
)
async def activate_version(
    game_id: UUID, version: int, user: CurrentUser, db: DbSession
) -> ApiResponse[GameResp]:
    """切换 current_version（Batch A · R4）。"""
    return ApiResponse(
        data=_to_resp(await services.activate_version(db, user, game_id, version))
    )


@router.get(
    "/{game_id}/reactions",
    response_model=ApiResponse[ReactionStateResp],
    responses=ERR_404,
)
async def get_reaction_state(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[ReactionStateResp]:
    """读取当前用户对该游戏的点赞/收藏态 + 公开计数（Batch C · R7）。"""
    return ApiResponse(
        data=await reaction_services.get_reaction_state(db, user, game_id)
    )


@router.post(
    "/{game_id}/like",
    response_model=ApiResponse[ReactionToggleResp],
    responses=ERR_404,
)
async def toggle_like(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[ReactionToggleResp]:
    return ApiResponse(
        data=await reaction_services.toggle_reaction(db, user, game_id, ReactionType.LIKE)
    )


@router.delete(
    "/{game_id}/like",
    response_model=ApiResponse[ReactionToggleResp],
    responses=ERR_404,
)
async def unlike(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[ReactionToggleResp]:
    """幂等取消点赞（不存在则 noop），返回最新计数。"""
    return ApiResponse(
        data=await reaction_services.remove_reaction(db, user, game_id, ReactionType.LIKE)
    )


@router.post(
    "/{game_id}/favorite",
    response_model=ApiResponse[ReactionToggleResp],
    responses=ERR_404,
)
async def toggle_favorite(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[ReactionToggleResp]:
    return ApiResponse(
        data=await reaction_services.toggle_reaction(db, user, game_id, ReactionType.FAVORITE)
    )


@router.delete(
    "/{game_id}/favorite",
    response_model=ApiResponse[ReactionToggleResp],
    responses=ERR_404,
)
async def unfavorite(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[ReactionToggleResp]:
    """幂等取消收藏（不存在则 noop），返回最新计数。"""
    return ApiResponse(
        data=await reaction_services.remove_reaction(db, user, game_id, ReactionType.FAVORITE)
    )
