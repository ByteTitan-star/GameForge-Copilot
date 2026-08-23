"""站内通知端点（docs/04 MVP）。"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.deps import CurrentUser, DbSession
from app.core.response import ApiResponse, ErrorResponse
from app.notify import services
from app.schemas.notification import NotificationItem, NotificationReadResp

router = APIRouter(prefix="/me/notifications", tags=["notifications"])

ERR_404 = {404: {"model": ErrorResponse, "description": "通知不存在"}}


@router.get("", response_model=ApiResponse[list[NotificationItem]])
async def list_notifications(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = Query(False),
) -> ApiResponse[list[NotificationItem]]:
    """列出当前用户站内通知。

    作用：按时间倒序返回通知，可选仅未读。
    场景：通知中心铃铛下拉或列表页。
    参数：user — 当前用户；db — 数据库会话；unread_only — 是否仅未读。
    返回：ApiResponse，data 为 NotificationItem 列表。
    """
    rows = await services.list_notifications(db, user, unread_only=unread_only)
    return ApiResponse(
        data=[
            NotificationItem(
                id=n.id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                read=n.read,
                created_at=n.created_at,
            )
            for n in rows
        ]
    )


@router.post(
    "/{notification_id}/read",
    response_model=ApiResponse[NotificationReadResp],
    responses=ERR_404,
)
async def mark_read(
    notification_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[NotificationReadResp]:
    """将单条通知标为已读。

    作用：更新指定通知的 read 状态。
    场景：用户点开或批量已读某条通知。
    参数：notification_id — 通知 ID；user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data 含 id 与 read；不存在 404。
    """
    n = await services.mark_read(db, user, notification_id)
    return ApiResponse(data=NotificationReadResp(id=n.id, read=n.read))
