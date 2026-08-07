"""管理后台端点（M8）：用户管理 + 全局设置 + 审计 + 游戏列表，admin only。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.admin import services
from app.auth.deps import AdminUser, DbSession, RedisClient
from app.core.response import ApiResponse, ErrorResponse, PaginatedData
from app.enums import GameStatus, Role
from app.schemas.admin import (
    AdminGameItem,
    AdminSettings,
    AdminUserItem,
    AdminUserPatch,
    AuditLogItem,
)

router = APIRouter(prefix="/admin", tags=["admin"])

ERR_404 = {404: {"model": ErrorResponse, "description": "用户不存在"}}


@router.get("/users", response_model=PaginatedData[AdminUserItem])
async def list_users(
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[AdminUserItem]:
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
        total=total, page=page, size=size,
    )


@router.patch("/users/{user_id}", response_model=ApiResponse[AdminUserItem], responses=ERR_404)
async def patch_user(
    user_id: UUID,
    req: AdminUserPatch,
    admin: AdminUser,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[AdminUserItem]:
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


@router.get("/settings", response_model=ApiResponse[AdminSettings])
async def get_settings(admin: AdminUser, db: DbSession) -> ApiResponse[AdminSettings]:
    _ = admin
    return ApiResponse(data=await services.get_settings(db))


@router.put("/settings", response_model=ApiResponse[AdminSettings])
async def update_settings(
    admin: AdminUser, db: DbSession, req: AdminSettings
) -> ApiResponse[AdminSettings]:
    return ApiResponse(data=await services.update_settings(db, admin, req))


@router.get("/audit-logs", response_model=PaginatedData[AuditLogItem])
async def list_audit_logs(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[AuditLogItem]:
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
    """管理员游戏列表（不含草稿），默认含 published/submitted/reviewing/taken_down。"""
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
                updated_at=g.updated_at,
            )
            for g in rows
        ],
        total=total,
        page=page,
        size=size,
    )
