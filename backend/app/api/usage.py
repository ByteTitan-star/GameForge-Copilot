"""用量端点（M3 真实逻辑）：/me/usage + /admin/usage，从 Redis 读取真实累计。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.admin import services as admin_services
from app.auth.deps import AdminUser, CurrentUser, DbSession, RedisClient
from app.core.response import ApiResponse, ErrorResponse, PaginatedData
from app.games import services as game_services
from app.schemas.usage import (
    AdminAnalyticsResp,
    AdminUsageResp,
    AnalyticsTopItem,
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
async def my_usage(user: CurrentUser, r: RedisClient, db: DbSession) -> ApiResponse[UsageResp]:
    """读取当前用户 token 用量与日配额剩余。

    作用：从 Redis 聚合今日/本月/累计用量及配额信息。
    场景：个人中心用量页、forge 配额提示。
    参数：user — 当前用户；r — Redis；db — 读取生效日限额。
    返回：ApiResponse，data 为 UsageResp。
    """
    daily_default, _, _ = await admin_services.get_effective_limits(db)
    daily = await quota_mod.get_user_daily_limit(r, user.id, daily_default)
    return ApiResponse(data=await store.get_user_usage(r, user.id, daily))


@router.get("/admin/usage", responses={**ERR_401, **ERR_403})
async def admin_usage(
    user: AdminUser, r: RedisClient, db: DbSession
) -> ApiResponse[AdminUsageResp]:
    """读取全站用量总览与月榜 top 用户（admin only）。

    作用：聚合系统级用量与各用户当月 token 排行。
    场景：管理后台用量分析页。
    参数：user — 管理员；r — Redis；db — 补全用户邮箱。
    返回：ApiResponse，data 为 AdminUsageResp。
    """
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
    """分页列出用户用量按游戏或 run 的拆分明细。

    作用：scope=game|run 时列举当月有用量记录的维度及 USD 估算。
    场景：个人中心用量明细页。
    参数：user — 当前用户；r/db — 存储；scope — game 或 run；page/size — 分页。
    返回：PaginatedData，data 为 UsageBreakdownItem 列表。
    """
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
    """读取单游戏当月 token 用量与 USD 估算。

    作用：校验游戏归属后读取 Redis 游戏月桶并估算费用。
    场景：游戏详情页用量卡片。
    参数：game_id — 游戏 ID；user — 当前用户；r/db — 存储。
    返回：ApiResponse，data 为 GameUsageResp。
    """
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
    """读取单游戏的试玩统计（play_count + 近 30 日 PV/UV）。

    作用：合并 DB play_count 与 Redis 按 slug 的访问分析。
    场景：游戏详情页数据概览。
    参数：game_id — 游戏 ID；user — 当前用户；r/db — 存储。
    返回：ApiResponse，data 为 GameAnalyticsResp。
    """
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


@router.get("/admin/analytics/top", response_model=ApiResponse[AdminAnalyticsResp])
async def admin_analytics_top(
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse[AdminAnalyticsResp]:
    """读取全站访问分析：热门游戏榜 + 近 30 日趋势（admin only）。

    作用：按 play_count 取 top 已发布游戏，并聚合全站 PV/UV 趋势。
    场景：管理后台访问分析页。
    参数：admin — 管理员；db/r — 存储；limit — 榜单条数。
    返回：ApiResponse，data 为 AdminAnalyticsResp。
    """
    from sqlalchemy import select

    from app.analytics import store as analytics_store
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
        data=AdminAnalyticsResp(
            top_games=[
                AnalyticsTopItem(
                    game_id=g.id,
                    title=g.title,
                    slug=g.slug,
                    play_count=int(g.play_count or 0),
                )
                for g in rows
            ],
            trend=await analytics_store.site_trend(r, days=30),
        )
    )
