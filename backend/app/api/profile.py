"""用户资料端点（Batch C · R6）。"""

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession
from app.core.response import ApiResponse, ErrorResponse
from app.profile import services
from app.schemas.profile import ProfilePatch, UserProfile

router = APIRouter(prefix="/me/profile", tags=["profile"])

ERR_409 = {409: {"model": ErrorResponse, "description": "handle 冲突"}}
ERR_403 = {403: {"model": ErrorResponse, "description": "试用账号只读"}}


@router.get("", response_model=ApiResponse[UserProfile])
async def get_profile(user: CurrentUser, db: DbSession) -> ApiResponse[UserProfile]:
    """获取当前用户资料。

    作用：读取昵称、handle、头像等个人资料字段。
    场景：设置页或个人中心展示。
    参数：user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data 为 UserProfile。
    """
    return ApiResponse(data=await services.get_profile(db, user))


@router.patch("", response_model=ApiResponse[UserProfile], responses={**ERR_409, **ERR_403})
async def patch_profile(
    req: ProfilePatch, user: CurrentUser, db: DbSession
) -> ApiResponse[UserProfile]:
    """部分更新当前用户资料。

    作用：修改 display_name、handle 等可编辑字段。
    场景：用户编辑个人资料；试用账号只读 403，handle 冲突 409。
    参数：req — 待更新字段；user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data 为更新后的 UserProfile。
    """
    return ApiResponse(data=await services.patch_profile(db, user, req))
