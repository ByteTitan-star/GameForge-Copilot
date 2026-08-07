"""用量端点（M3 真实逻辑）：/me/usage + /admin/usage，从 Redis 读取真实累计。"""

from fastapi import APIRouter

from app.admin import services as admin_services
from app.auth.deps import AdminUser, CurrentUser, DbSession, RedisClient
from app.core.response import ApiResponse, ErrorResponse
from app.schemas.usage import AdminUsageResp, UsageResp
from app.usage import quota as quota_mod
from app.usage import store

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
