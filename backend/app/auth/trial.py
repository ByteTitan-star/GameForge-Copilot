"""试用预览账号（与前端 `lib/trial.ts` 邮箱/密码一致，须 seed 后方能登录）。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.core.errors import AppError, ErrorCode
from app.enums import Role
from app.models.user import User

TRIAL_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
TRIAL_EMAIL = "demo@gameforge.dev"
TRIAL_PASSWORD = "password123"


def is_trial_user(user: User) -> bool:
    """共享试用账号：按固定 id 或邮箱识别（与前端 lib/trial.ts 一致）。"""
    return user.id == TRIAL_USER_ID or user.email.strip().lower() == TRIAL_EMAIL


def reject_trial_mutation(user: User) -> None:
    """试用账号只读：密码、资料等账号级变更一律 403。"""
    if is_trial_user(user):
        raise AppError(ErrorCode.FORBIDDEN, "试用预览账号为只读，不能修改账号信息")


async def ensure_trial_user(db: AsyncSession) -> User:
    """幂等创建试用账号：已验证邮箱、可多人各自登录（独立 refresh token）。"""
    user = await db.get(User, TRIAL_USER_ID)
    if user is not None:
        return user
    by_email = await db.scalar(select(User).where(User.email == TRIAL_EMAIL))
    if by_email is not None:
        return by_email
    user = User(
        id=TRIAL_USER_ID,
        email=TRIAL_EMAIL,
        password_hash=hash_password(TRIAL_PASSWORD),
        role=Role.USER.value,
        email_verified=True,
        disabled=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
