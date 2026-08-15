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
    return ApiResponse(data=await services.get_profile(db, user))


@router.patch("", response_model=ApiResponse[UserProfile], responses={**ERR_409, **ERR_403})
async def patch_profile(
    req: ProfilePatch, user: CurrentUser, db: DbSession
) -> ApiResponse[UserProfile]:
    return ApiResponse(data=await services.patch_profile(db, user, req))
