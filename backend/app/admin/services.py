"""管理后台：用户管理 + 全局设置 + 审计 + 已发布游戏列表（admin）。"""

import uuid
from datetime import datetime

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus, Role
from app.models.audit_log import AuditLog
from app.models.game import Game
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.admin import AdminSettings
from app.usage import quota as quota_mod

_LIMITS_KEY = "limits"
_GENERAL_KEY = "general"


async def get_admin_contact_email(db: AsyncSession) -> str:
    """禁用账号登录提示中的管理员邮箱：DB 设置 > 环境变量 > 首个可用管理员。"""
    row = await db.get(SystemSetting, _GENERAL_KEY)
    if row is not None:
        contact = (row.value or {}).get("admin_contact_email", "").strip()
        if contact:
            return contact
    if settings.admin_contact_email.strip():
        return settings.admin_contact_email.strip()
    admins = await list_admin_emails(db)
    if admins:
        return admins[0]
    return "admin@example.com"


async def disabled_user_message(db: AsyncSession) -> str:
    contact = await get_admin_contact_email(db)
    return f"当前账号已违规，请联系管理员<{contact}>申请解封"


async def _active_admin_count(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(User).where(
                User.role == Role.ADMIN.value,
                User.disabled.is_(False),
            )
        )
        or 0
    )


async def list_users(
    db: AsyncSession, page: int, size: int
) -> tuple[list[User], int]:
    base = select(User)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(User.created_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def user_daily_limits(
    r: redis.Redis, users: list[User]
) -> dict[uuid.UUID, int | None]:
    out: dict[uuid.UUID, int | None] = {}
    for u in users:
        raw = await r.get(f"quota:user:{u.id}")
        out[u.id] = int(raw) if raw is not None else None
    return out


async def patch_user(
    db: AsyncSession,
    r: redis.Redis,
    admin: User,
    user_id: uuid.UUID,
    role: Role | None,
    disabled: bool | None,
    daily_token_limit: int | None = None,
    *,
    set_daily_limit: bool = False,
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "用户不存在")
    if disabled is True and user.id == admin.id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不能禁用当前登录的管理员账号")
    if (
        role is not None
        and role != Role.ADMIN
        and user.role == Role.ADMIN.value
        and await _active_admin_count(db) <= 1
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "至少保留一名可用管理员")
    detail: dict = {}
    if role is not None:
        user.role = role.value
        detail["role"] = role.value
    if disabled is not None:
        user.disabled = disabled
        detail["disabled"] = disabled
    if set_daily_limit:
        await quota_mod.set_user_daily_limit(r, user_id, daily_token_limit)
        detail["daily_token_limit"] = daily_token_limit
    db.add(AuditLog(actor_id=admin.id, action="update_user", target=str(user_id), detail=detail))
    await db.commit()
    return user


async def delete_user(
    db: AsyncSession,
    r: redis.Redis,
    admin: User,
    user_id: uuid.UUID,
) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "用户不存在")
    if user.id == admin.id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不能删除当前登录的管理员账号")
    if user.role == Role.ADMIN.value and await _active_admin_count(db) <= 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "至少保留一名可用管理员")
    email = user.email
    await db.delete(user)
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="delete_user",
            target=str(user_id),
            detail={"email": email},
        )
    )
    await db.commit()
    await r.delete(f"quota:user:{user_id}")


async def get_settings(db: AsyncSession) -> AdminSettings:
    daily, monthly, rate = await get_effective_limits(db)
    return AdminSettings(
        default_daily_token_limit=daily,
        default_monthly_token_limit=monthly,
        default_rate_limit_per_min=rate,
        admin_contact_email=await get_admin_contact_email(db),
    )


async def update_settings(db: AsyncSession, admin: User, req: AdminSettings) -> AdminSettings:
    row = await db.get(SystemSetting, _LIMITS_KEY)
    value = {
        "default_daily_token_limit": req.default_daily_token_limit,
        "default_monthly_token_limit": req.default_monthly_token_limit,
        "default_rate_limit_per_min": req.default_rate_limit_per_min,
    }
    if row is None:
        row = SystemSetting(key=_LIMITS_KEY, value=value, updated_by=admin.id)
        db.add(row)
    else:
        row.value = value
        row.updated_by = admin.id
    general = await db.get(SystemSetting, _GENERAL_KEY)
    general_value = {"admin_contact_email": req.admin_contact_email.strip()}
    if general is None:
        db.add(
            SystemSetting(key=_GENERAL_KEY, value=general_value, updated_by=admin.id)
        )
    else:
        general.value = general_value
        general.updated_by = admin.id
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="update_settings",
            target=_LIMITS_KEY,
            detail={**value, **general_value},
        )
    )
    await db.commit()
    return req


async def get_effective_limits(db: AsyncSession) -> tuple[int, int, int]:
    """返回 (daily, monthly, rate_per_min)。DB 覆盖优先。"""
    row = await db.get(SystemSetting, _LIMITS_KEY)
    if row is not None:
        v = row.value or {}
        return (
            int(v.get("default_daily_token_limit", settings.default_daily_token_limit)),
            int(v.get("default_monthly_token_limit", settings.default_monthly_token_limit)),
            int(v.get("default_rate_limit_per_min", settings.default_rate_limit_per_min)),
        )
    return (
        settings.default_daily_token_limit,
        settings.default_monthly_token_limit,
        settings.default_rate_limit_per_min,
    )


async def list_audit_logs(
    db: AsyncSession, page: int, size: int
) -> tuple[list[AuditLog], int]:
    base = select(AuditLog)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(AuditLog.created_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def list_admin_games(
    db: AsyncSession,
    status: GameStatus | None,
    page: int,
    size: int,
) -> tuple[list[Game], int]:
    """管理员可见：默认 published；也可查 taken_down 等公开管理态（不含 draft）。"""
    allowed = {
        GameStatus.PUBLISHED,
        GameStatus.TAKEN_DOWN,
        GameStatus.SUBMITTED,
        GameStatus.REVIEWING,
    }
    base = select(Game).where(Game.status.in_([s.value for s in allowed]))
    if status is not None:
        if status not in allowed:
            raise AppError(ErrorCode.VALIDATION_ERROR, "admin 不可按此状态筛选草稿")
        base = select(Game).where(Game.status == status.value)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(Game.updated_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def list_admin_emails(db: AsyncSession) -> list[str]:
    rows = (
        await db.scalars(
            select(User).where(User.role == Role.ADMIN.value, User.disabled.is_(False))
        )
    ).all()
    return [u.email for u in rows]


async def patch_game_schedule(
    db: AsyncSession,
    admin: User,
    game_id: uuid.UUID,
    scheduled_take_down_at: datetime | None,
    scheduled_publish_at: datetime | None,
) -> Game:
    game = await db.get(Game, game_id)
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在")
    game.scheduled_take_down_at = scheduled_take_down_at
    game.scheduled_publish_at = scheduled_publish_at
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="schedule_game",
            target=str(game_id),
            detail={
                "scheduled_take_down_at": scheduled_take_down_at.isoformat()
                if scheduled_take_down_at
                else None,
                "scheduled_publish_at": scheduled_publish_at.isoformat()
                if scheduled_publish_at
                else None,
            },
        )
    )
    await db.commit()
    await db.refresh(game)
    return game
