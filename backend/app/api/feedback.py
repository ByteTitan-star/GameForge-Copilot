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
    """代发用户反馈邮件给管理员。

    作用：校验 run 归属后，将反馈内容通过邮件队列发送给管理员。
    场景：forge 失败时「联系管理员」入口。
    参数：req — 反馈内容与关联 run_id；request — 取客户端 IP 限流；user/db/r — 鉴权与存储。
    返回：ApiResponse，data 为 FeedbackResp；run 不可见 404，限流 429。
    """
    ip = request.client.host if request.client else "na"
    resp = await services.submit_feedback(db, r, user, ip, req)
    return ApiResponse(data=resp)
