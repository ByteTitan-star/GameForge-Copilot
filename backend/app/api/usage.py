"""用量端点（M3 真实逻辑）：/me/usage + /admin/usage，从 Redis 读取真实累计。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.admin import services as admin_services
from app.auth.deps import AdminUser, CurrentUser, DbSession, RedisClient
from app.core.response import ApiResponse, ErrorResponse, PaginatedData
from app.games import services as game_services
from app.schemas.usage import (
    AdminUsageResp,
    GameAnalyticsResp,
    GameUsageResp,
    UsageBreakdownItem,
    UsageResp,
)
from app.usage import quota as quota_mod
from app.usage import store
from app.usage.pricing import estimate_usd

router = APIRouter(tags=["usage"])

ERR_401 = {401: {"model": ErrorResponse, "description": "未认证"}}
ERR_403 = {403: {"model": ErrorResponse, "description": "无权限"}}


@router.get("/me/usage", response_model=ApiResponse[UsageResp], responses=ERR_401)
async def my_usage(
    user: CurrentUser, r: RedisClient, db: DbSession
) -> ApiResponse[UsageResp]:
    daily_default, _, _ = await admin_services.get_effective_limits(db)
    daily = await quota_mod.get_user_daily_limit(r, user.id, daily_default)
    return ApiResponse(data=await store.get_user_usage(r, user.id, daily))


@router.get("/admin/usage", responses={**ERR_401, **ERR_403})
async def admin_usage(
    user: AdminUser, r: RedisClient, db: DbSession
) -> ApiResponse[AdminUsageResp]:
    _ = user  # require_admin 已校验角色
    return ApiResponse(data=await store.get_admin_usage(r, db))


@router.get("/me/usage/breakdown", response_model=PaginatedData[UsageBreakdownItem])
async def usage_breakdown(
    user: CurrentUser,
    r: RedisClient,
    db: DbSession,
    scope: str = Query("game", pattern="^(game|run)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[UsageBreakdownItem]:
    rows, total = await store.list_usage_breakdown(r, db, user.id, scope, page, size)
    return PaginatedData(
        data=[UsageBreakdownItem.model_validate(x) for x in rows],
        total=total,
        page=page,
        size=size,
    )


@router.get("/games/{game_id}/usage", response_model=ApiResponse[GameUsageResp], responses=ERR_401)
async def game_usage(
    game_id: UUID, user: CurrentUser, r: RedisClient, db: DbSession
) -> ApiResponse[GameUsageResp]:
    game = await game_services.get_owned_game(db, user, game_id)
    bucket = await store.get_game_usage(r, game.id)
    usd = estimate_usd(
        "openai_compat",
        "default",
        input_tokens=bucket.input_tokens,
        output_tokens=bucket.output_tokens,
    )
    return ApiResponse(
        data=GameUsageResp(game_id=game.id, month=bucket, estimated_usd=round(usd, 6))
    )


@router.get("/games/{game_id}/analytics", response_model=ApiResponse[GameAnalyticsResp])
async def game_analytics(
    game_id: UUID, user: CurrentUser, r: RedisClient, db: DbSession
) -> ApiResponse[GameAnalyticsResp]:
    from app.analytics import store as analytics_store

    game = await game_services.get_owned_game(db, user, game_id)
    slug = game.slug or ""
    stats = await analytics_store.game_analytics(r, slug) if slug else {"pv_30d": 0, "uv_30d": 0}
    return ApiResponse(
        data=GameAnalyticsResp(
            game_id=game.id,
            play_count=int(game.play_count or 0),
            pv_30d=stats["pv_30d"],
            uv_30d=stats["uv_30d"],
        )
    )


@router.get("/admin/analytics/top")
async def admin_analytics_top(
    admin: AdminUser,
    db: DbSession,
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse[list[dict]]:
    from sqlalchemy import select

    from app.enums import GameStatus
    from app.models.game import Game

    _ = admin
    rows = (
        await db.scalars(
            select(Game)
            .where(Game.status == GameStatus.PUBLISHED.value)
            .order_by(Game.play_count.desc())
            .limit(limit)
        )
    ).all()
    return ApiResponse(
        data=[
            {
                "game_id": g.id,
                "title": g.title,
                "slug": g.slug,
                "play_count": int(g.play_count or 0),
            }
            for g in rows
        ]
    )
