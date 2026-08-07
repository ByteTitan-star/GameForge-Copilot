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
    row = await db.get(Notification, notif_id)
    if row is None or row.user_id != user.id:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "通知不存在")
    row.read = True
    await db.commit()
    await db.refresh(row)
    return row
