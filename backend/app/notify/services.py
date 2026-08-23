"""站内通知：写入 DB + 可选邮件（docs/04）。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.email import queue as email_queue
from app.models.notification import Notification
from app.models.user import User


async def notify_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    kind: str,
    title: str,
    body: str,
    email: str | None = None,
    send_email: bool = True,
) -> Notification:
    """写入站内通知并可选发送邮件。

    作用：创建 Notification 行；send_email=True 且提供 email 时入队邮件。
    场景：发布审批、下架、配额告警等业务通知。
    参数：db — 数据库会话；user_id — 收件用户；kind/title/body — 通知内容；
        email — 可选邮箱；send_email — 是否发邮件。
    返回：持久化后的 Notification 实例。
    """
    row = Notification(user_id=user_id, kind=kind, title=title, body=body)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    if send_email and email:
        await email_queue.enqueue_notification(email, title, body)
    return row


async def list_notifications(
    db: AsyncSession, user: User, *, unread_only: bool = False, limit: int = 50
) -> list[Notification]:
    """列出用户站内通知。

    作用：按创建时间倒序，可选仅未读，默认最多 50 条。
    场景：GET /me/notifications 路由调用。
    参数：db — 数据库会话；user — 当前用户；unread_only — 是否仅未读；limit — 条数上限。
    返回：Notification 列表。
    """
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    return list((await db.scalars(stmt)).all())


async def mark_read(db: AsyncSession, user: User, notif_id: uuid.UUID) -> Notification:
    """将单条通知标为已读。

    作用：更新指定通知的 read=True，校验归属。
    场景：POST /me/notifications/{id}/read 路由调用。
    参数：db — 数据库会话；user — 当前用户；notif_id — 通知 ID。
    返回：更新后的 Notification；不存在或非本人 404。
    """
    row = await db.get(Notification, notif_id)
    if row is None or row.user_id != user.id:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "通知不存在")
    row.read = True
    await db.commit()
    await db.refresh(row)
    return row
