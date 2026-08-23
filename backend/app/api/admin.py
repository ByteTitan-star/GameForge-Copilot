"""管理后台端点（M8）：用户管理 + 全局设置 + 审计 + 游戏列表，admin only。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.admin import services
from app.auth.deps import AdminUser, DbSession, RedisClient
from app.auth.ratelimit import check_rate_limit
from app.core.config import settings
from app.core.response import ApiResponse, ErrorResponse, PaginatedData
from app.enums import GameStatus, LLMProvider, Role
from app.llm import provider as llm_provider
from app.schemas.admin import (
    AdminAuditLlmSettings,
    AdminAuditLlmTestResp,
    AdminGameFeaturedPatch,
    AdminGameItem,
    AdminGameSchedulePatch,
    AdminSettings,
    AdminUserItem,
    AdminUserPatch,
    AuditLogItem,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ERR_404 = {404: {"model": ErrorResponse, "description": "用户不存在"}}
ERR_429 = {429: {"model": ErrorResponse, "description": "探测限流"}}


@router.get("/users", response_model=PaginatedData[AdminUserItem])
async def list_users(
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[AdminUserItem]:
    """分页列出全部用户（含日 token 限额覆盖）。

    作用：返回用户列表及每人 Redis 配额覆盖值。
    场景：管理后台用户管理页。
    参数：admin — 管理员；db/r — 数据库与 Redis；page/size — 分页。
    返回：PaginatedData，data 为 AdminUserItem 列表。
    """
    _ = admin
    rows, total = await services.list_users(db, page, size)
    limits = await services.user_daily_limits(r, rows)
    return PaginatedData(
        data=[
            AdminUserItem(
                user_id=u.id,
                email=u.email,
                role=Role(u.role),
                email_verified=u.email_verified,
                disabled=u.disabled,
                created_at=u.created_at,
                daily_token_limit=limits.get(u.id),
            )
            for u in rows
        ],
        total=total,
        page=page,
        size=size,
    )


@router.patch("/users/{user_id}", response_model=ApiResponse[AdminUserItem], responses=ERR_404)
async def patch_user(
    user_id: UUID,
    req: AdminUserPatch,
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[AdminUserItem]:
    """管理员修改用户角色、禁用状态或日 token 限额。

    作用：更新用户字段；daily_token_limit 仅在 body 含该字段时写入（null 清除覆盖）。
    场景：PATCH /admin/users/{id}。
    参数：user_id — 目标用户；req — 待更新字段；admin/db/r — 操作者与存储。
    返回：ApiResponse，data 为更新后的 AdminUserItem；不存在 404。
    """
    # daily_token_limit：字段出现在 body 才更新（含显式 null 清覆盖）
    set_limit = "daily_token_limit" in req.model_fields_set
    u = await services.patch_user(
        db,
        r,
        admin,
        user_id,
        req.role,
        req.disabled,
        req.daily_token_limit,
        set_daily_limit=set_limit,
    )
    limit = await services.user_daily_limits(r, [u])
    return ApiResponse(
        data=AdminUserItem(
            user_id=u.id,
            email=u.email,
            role=Role(u.role),
            email_verified=u.email_verified,
            disabled=u.disabled,
            created_at=u.created_at,
            daily_token_limit=limit.get(u.id),
        )
    )


@router.delete("/users/{user_id}", status_code=204, responses=ERR_404)
async def delete_user(
    user_id: UUID,
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
) -> None:
    """管理员删除用户账号。

    作用：物理删除用户并清除 Redis 配额键，记审计日志。
    场景：DELETE /admin/users/{id}。
    参数：user_id — 目标用户；admin/db/r — 操作者与存储。
    返回：204 无 body；不可删自己或唯一管理员时 400。
    """
    await services.delete_user(db, r, admin, user_id)


@router.get("/settings", response_model=ApiResponse[AdminSettings])
async def get_settings(admin: AdminUser, db: DbSession) -> ApiResponse[AdminSettings]:
    """读取全局 admin 设置。

    作用：返回限额默认值、联系邮箱、审核模型回显（apikey 脱敏）。
    场景：管理后台全局设置页。
    参数：admin — 管理员；db — 数据库会话。
    返回：ApiResponse，data 为 AdminSettings。
    """
    _ = admin
    return ApiResponse(data=await services.get_settings(db))


@router.put("/settings", response_model=ApiResponse[AdminSettings])
async def update_settings(
    admin: AdminUser, db: DbSession, req: AdminSettings
) -> ApiResponse[AdminSettings]:
    """更新全局 admin 设置。

    作用：写入限额、联系邮箱、审核模型配置并记审计。
    场景：PUT /admin/settings。
    参数：admin — 操作者；db — 数据库会话；req — 新设置体。
    返回：ApiResponse，data 为提交后的 AdminSettings。
    """
    return ApiResponse(data=await services.update_settings(db, admin, req))


@router.post(
    "/settings/audit-llm/test",
    response_model=ApiResponse[AdminAuditLlmTestResp],
    responses=ERR_429,
)
async def test_audit_llm(
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
    req: AdminAuditLlmSettings,
) -> ApiResponse[AdminAuditLlmTestResp]:
    """审核模型连通测试（表单当前值 dry-test，不落库）。

    作用：用最小 completion 验证 provider/model/apikey/base_url。
    场景：管理后台保存前测试审核 LLM；apikey 为空或含 *** 时回退 DB 已存密钥。
    参数：admin/db/r — 操作者与存储；req — 审核模型表单值。
    返回：ApiResponse，data.tested_ok 与可选 error；限流 429。
    """
    await check_rate_limit(
        r,
        f"rl:llm-probe:{admin.id}",
        settings.llm_probe_rate_limit_per_min,
        60,
    )
    apikey = req.apikey.strip()
    if not apikey or "***" in apikey:
        cfg = await services.get_audit_llm_config(db)
        apikey = cfg["apikey"]
    try:
        prov = LLMProvider(req.provider)
    except ValueError:
        prov = LLMProvider.OPENAI_COMPAT
    ok, err = await llm_provider.test_connectivity(
        prov,
        apikey,
        req.model.strip(),
        req.base_url.strip() or None,
    )
    return ApiResponse(data=AdminAuditLlmTestResp(tested_ok=ok, error=err))


@router.get("/audit-logs", response_model=PaginatedData[AuditLogItem])
async def list_audit_logs(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[AuditLogItem]:
    """分页列出管理员审计日志。

    作用：按时间倒序返回 audit_logs 记录。
    场景：管理后台审计日志页。
    参数：admin — 管理员；db — 数据库会话；page/size — 分页。
    返回：PaginatedData，data 为 AuditLogItem 列表。
    """
    _ = admin
    rows, total = await services.list_audit_logs(db, page, size)
    return PaginatedData(
        data=[
            AuditLogItem(
                id=a.id,
                actor_id=a.actor_id,
                action=a.action,
                target=a.target,
                detail=a.detail,
                created_at=a.created_at,
            )
            for a in rows
        ],
        total=total,
        page=page,
        size=size,
    )


@router.get("/games", response_model=PaginatedData[AdminGameItem])
async def list_admin_games(
    admin: AdminUser,
    db: DbSession,
    status: GameStatus | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[AdminGameItem]:
    """管理员游戏列表（不含草稿）。

    作用：筛选 published/taken_down/submitted/reviewing 态游戏。
    场景：管理后台游戏管理页；可选 status 过滤。
    参数：admin — 管理员；db — 数据库会话；status — 可选状态；page/size — 分页。
    返回：PaginatedData，data 为 AdminGameItem 列表。
    """
    _ = admin
    rows, total = await services.list_admin_games(db, status, page, size)
    return PaginatedData(
        data=[
            AdminGameItem(
                game_id=g.id,
                title=g.title,
                status=GameStatus(g.status),
                slug=g.slug,
                owner_id=g.owner_id,
                current_version=g.current_version,
                featured=g.featured_rank is not None,
                updated_at=g.updated_at,
            )
            for g in rows
        ],
        total=total,
        page=page,
        size=size,
    )


@router.patch(
    "/games/{game_id}/schedule",
    response_model=ApiResponse[AdminGameItem],
    responses=ERR_404,
)
async def patch_game_schedule(
    game_id: UUID,
    req: AdminGameSchedulePatch,
    admin: AdminUser,
    db: DbSession,
) -> ApiResponse[AdminGameItem]:
    """设置游戏定时下架/上架时间。

    作用：更新 scheduled_take_down_at 与 scheduled_publish_at。
    场景：管理后台定时上下架配置；scheduler 到期自动执行。
    参数：game_id — 游戏 ID；req — 计划时间；admin/db — 操作者与存储。
    返回：ApiResponse，data 为 AdminGameItem；不存在 404。
    """
    g = await services.patch_game_schedule(
        db,
        admin,
        game_id,
        req.scheduled_take_down_at,
        req.scheduled_publish_at,
    )
    return ApiResponse(
        data=AdminGameItem(
            game_id=g.id,
            title=g.title,
            status=GameStatus(g.status),
            slug=g.slug,
            owner_id=g.owner_id,
            current_version=g.current_version,
            featured=g.featured_rank is not None,
            updated_at=g.updated_at,
        )
    )


@router.patch(
    "/games/{game_id}/featured",
    response_model=ApiResponse[AdminGameItem],
    responses=ERR_404,
)
async def patch_game_featured(
    game_id: UUID,
    req: AdminGameFeaturedPatch,
    admin: AdminUser,
    db: DbSession,
) -> ApiResponse[AdminGameItem]:
    """设置或取消游戏精选排序位。

    作用：更新 featured_rank（None 表示取消精选）。
    场景：管理后台精选游戏配置。
    参数：game_id — 游戏 ID；req.featured_rank — 排序值或 None；admin/db — 操作者与存储。
    返回：ApiResponse，data 为 AdminGameItem；非 published 或不存在时报错。
    """
    g = await services.patch_game_featured(db, admin, game_id, req.featured_rank)
    return ApiResponse(
        data=AdminGameItem(
            game_id=g.id,
            title=g.title,
            status=GameStatus(g.status),
            slug=g.slug,
            owner_id=g.owner_id,
            current_version=g.current_version,
            featured=g.featured_rank is not None,
            updated_at=g.updated_at,
        )
    )
