"""试用预览账号（与前端 `lib/trial.ts` 邮箱/密码一致，须 seed 后方能登录）。"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.core.errors import AppError, ErrorCode
from app.enums import Role
from app.models.game_reaction import GameReaction
from app.models.user import User

TRIAL_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
TRIAL_EMAIL = "demo@gameforge.dev"
TRIAL_PASSWORD = "password123"  # nosec B105 — documented demo account, must match frontend trial.ts


def is_trial_user(user: User) -> bool:
    """判断是否为共享试用账号。

    作用：按固定 TRIAL_USER_ID 或 TRIAL_EMAIL 识别。
    场景：试用账号只读守卫、密码重置跳过等。
    参数：user — 用户 ORM 行。
    返回：是试用账号为 True。
    """
    return user.id == TRIAL_USER_ID or user.email.strip().lower() == TRIAL_EMAIL


def reject_trial_mutation(user: User) -> None:
    """拒绝试用账号的账号级变更。

    作用：试用账号修改密码/资料等一律 403。
    场景：change_password、patch_profile 等业务入口。
    参数：user — 当前用户。
    返回：无；试用用户抛 FORBIDDEN。
    """
    if is_trial_user(user):
        raise AppError(ErrorCode.FORBIDDEN, "试用预览账号为只读，不能修改账号信息")


async def purge_trial_reactions(db: AsyncSession) -> int:
    """清理试用账号的点赞/收藏记录。

    作用：DELETE 该用户全部 GameReaction 行。
    场景：ensure_trial_user 时避免多人试用互相污染。
    参数：db — 数据库会话。
    返回：删除行数；用户不存在返回 0。
    """
    user = await db.get(User, TRIAL_USER_ID)
    if user is None:
        return 0
    result = await db.execute(delete(GameReaction).where(GameReaction.user_id == user.id))
    await db.commit()
    return int(result.rowcount or 0)


async def ensure_trial_user(db: AsyncSession) -> User:
    """幂等创建或返回试用账号。

    作用：按固定 ID/邮箱创建已验证试用用户，并清理 reactions。
    场景：应用启动 seed 或开发环境初始化。
    参数：db — 数据库会话。
    返回：试用 User ORM 实例。
    """
    user = await db.get(User, TRIAL_USER_ID)
    if user is not None:
        await purge_trial_reactions(db)
        return user
    by_email = await db.scalar(select(User).where(User.email == TRIAL_EMAIL))
    if by_email is not None:
        await purge_trial_reactions(db)
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
