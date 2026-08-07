"""游戏端点（M4 真实逻辑）：CRUD + versions + 可见性（owner 过滤）。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.deps import CurrentUser, DbSession
from app.core.response import ApiResponse, ErrorResponse, PaginatedData
from app.enums import GameStatus
from app.games import services
from app.models.game import Game
from app.models.game_version import GameVersion
from app.schemas.game import (
    GameCreate,
    GameDeleteResp,
    GameDetailResp,
    GameListItem,
    GamePatch,
    GameResp,
    VersionItem,
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
    return GameListItem(
        game_id=game.id,
        title=game.title,
        status=GameStatus(game.status),
        current_version=game.current_version,
        slug=game.slug,
        updated_at=game.updated_at,
    )


def _to_version(v: GameVersion) -> VersionItem:
    return VersionItem(version=v.version, artifact_path=v.artifact_path, created_at=v.created_at)


@router.post("", response_model=ApiResponse[GameResp], status_code=201, responses=ERR_403)
async def create_game(req: GameCreate, user: CurrentUser, db: DbSession) -> ApiResponse[GameResp]:
    return ApiResponse(data=_to_resp(await services.create_game(db, user, req)))


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
