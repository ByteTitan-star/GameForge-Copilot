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
    n = await services.mark_read(db, user, notification_id)
    return ApiResponse(data=NotificationReadResp(id=n.id, read=n.read))
