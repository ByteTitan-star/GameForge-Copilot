"""公开创作者主页（Batch C · R6）。"""

from fastapi import APIRouter

from app.auth.deps import DbSession
from app.core.response import ApiResponse, ErrorResponse
from app.profile import services
from app.schemas.profile import CreatorProfile

router = APIRouter(prefix="/u", tags=["creator"])

ERR_404 = {404: {"model": ErrorResponse, "description": "创作者不存在或未公开"}}


@router.get("/{handle}", response_model=ApiResponse[CreatorProfile], responses=ERR_404)
async def get_creator(handle: str, db: DbSession) -> ApiResponse[CreatorProfile]:
    """按 handle 获取公开创作者主页。

    作用：返回创作者公开资料与作品摘要。
    场景：创作者主页 /u/{handle}，无需登录。
    参数：handle — 创作者唯一标识；db — 数据库会话。
    返回：ApiResponse，data 为 CreatorProfile；不存在则 404。
    """
    return ApiResponse(data=await services.get_public_creator(db, handle))
