"""用户反馈端点：forge 失败时「联系管理员」代发邮件。"""

from fastapi import APIRouter, Request

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.response import ApiResponse, ErrorResponse
from app.feedback import services
from app.schemas.feedback import FeedbackReq, FeedbackResp

router = APIRouter(prefix="/me", tags=["feedback"])

ERR_404 = {404: {"model": ErrorResponse, "description": "run 不存在或不可见"}}
ERR_429 = {429: {"model": ErrorResponse, "description": "限流"}}


@router.post(
    "/feedback",
    response_model=ApiResponse[FeedbackResp],
    responses={**ERR_404, **ERR_429},
)
async def submit_feedback(
    req: FeedbackReq,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[FeedbackResp]:
    """代发一封反馈邮件给管理员；run 必须属于当前用户。"""
    ip = request.client.host if request.client else "na"
    resp = await services.submit_feedback(db, r, user, ip, req)
    return ApiResponse(data=resp)
