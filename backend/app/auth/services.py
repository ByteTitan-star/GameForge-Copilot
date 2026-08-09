"""认证业务逻辑：路由薄，逻辑聚此，单函数 ≤50 行。"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.services import disabled_user_message
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.auth.tokens import issue_refresh, revoke_refresh, rotate_refresh
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import Role
from app.models.email_verification import EmailVerification
from app.models.password_reset import PasswordResetToken
from app.models.user import User


def _hash_token(token: str) -> str:
    """验证/重置 token 仅存 sha256（高熵随机串，argon2 无必要）。"""
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    """sqlite 返回 naive datetime，按 UTC 归一；pg 则已 aware。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _gen_verification_code() -> str:
    """6 位数字验证码（000000–999999，首位可为 0）。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def _gen_token() -> str:
    """密码重置等高熵链接 token。"""
    return secrets.token_urlsafe(32)


async def _invalidate_pending_verifications(db: AsyncSession, user_id: uuid.UUID) -> None:
    rows = (
        await db.scalars(
            select(EmailVerification).where(
                EmailVerification.user_id == user_id,
                EmailVerification.used_at.is_(None),
            )
        )
    ).all()
    now = _utcnow()
    for row in rows:
        row.used_at = now
    if rows:
        await db.commit()


async def _issue_verification_code(db: AsyncSession, user_id: uuid.UUID) -> str:
    code = _gen_verification_code()
    db.add(
        EmailVerification(
            user_id=user_id,
            token_hash=_hash_token(code),
            expires_at=_utcnow() + timedelta(seconds=settings.verify_email_ttl),
        )
    )
    await db.commit()
    return code


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    """注册即视为邮箱已验证：本项目无计费、邮箱仅用于通知，无需验证步骤。"""
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=Role.USER.value,
        email_verified=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise AppError(ErrorCode.EMAIL_TAKEN, "邮箱已注册") from e
    await db.refresh(user)
    return user


async def resend_verification(db: AsyncSession, email: str) -> str | None:
    """未验证用户重发验证码；已验证/不存在返回 None（防枚举）。"""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or user.email_verified:
        return None
    await _invalidate_pending_verifications(db, user.id)
    return await _issue_verification_code(db, user.id)


async def verify_email(db: AsyncSession, email: str, code: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "验证码无效或已过期")
    if user.email_verified:
        raise AppError(ErrorCode.VALIDATION_ERROR, "邮箱已验证")
    row = await db.scalar(
        select(EmailVerification).where(
            EmailVerification.user_id == user.id,
            EmailVerification.token_hash == _hash_token(code),
        )
    )
    if row is None or row.used_at is not None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "验证码无效或已过期")
    if _utcnow() > _aware(row.expires_at):
        raise AppError(ErrorCode.VALIDATION_ERROR, "验证码已过期")
    row.used_at = _utcnow()
    user.email_verified = True
    await db.commit()
    return user


async def login_user(
    db: AsyncSession, r: redis.Redis, email: str, password: str
) -> tuple[User, str, str]:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(ErrorCode.UNAUTHORIZED, "邮箱或密码错误")
    return await issue_session(db, r, user)


async def issue_session(
    db: AsyncSession, r: redis.Redis, user: User
) -> tuple[User, str, str]:
    if user.disabled:
        raise AppError(ErrorCode.FORBIDDEN, await disabled_user_message(db))
    access = create_access_token(user_id=user.id, role=user.role)
    refresh = await issue_refresh(r, user.id)
    return user, access, refresh


async def refresh_tokens(
    db: AsyncSession, r: redis.Redis, refresh_token: str
) -> tuple[str, str]:
    rotated = await rotate_refresh(r, refresh_token)
    if rotated is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "refresh token 无效")
    user_id, new_refresh = rotated
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "refresh token 无效")
    if user.disabled:
        raise AppError(ErrorCode.FORBIDDEN, await disabled_user_message(db))
    access = create_access_token(user_id=user.id, role=user.role)
    return access, new_refresh


async def logout(r: redis.Redis, refresh_token: str) -> None:
    await revoke_refresh(r, refresh_token)


async def request_password_reset(
    db: AsyncSession, email: str
) -> tuple[str, str] | None:
    """防枚举：用户不存在时返回 None，调用方仍恒返回 sent=true。"""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        return None
    token = _gen_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.password_reset_ttl),
        )
    )
    await db.commit()
    return user.email, token


async def confirm_password_reset(
    db: AsyncSession, token: str, new_password: str
) -> User:
    row = await _consume_token(db, PasswordResetToken, token)
    user = await db.get(User, row.user_id)
    if user is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 无效")
    user.password_hash = hash_password(new_password)
    await db.commit()
    return user


async def change_password(
    user: User, db: AsyncSession, old_password: str, new_password: str
) -> User:
    """登录态改密：旧密码错误 → 401；成功写新 hash。"""
    if not verify_password(old_password, user.password_hash):
        raise AppError(ErrorCode.UNAUTHORIZED, "旧密码不正确")
    if old_password == new_password:
        raise AppError(ErrorCode.VALIDATION_ERROR, "新密码不能与旧密码相同")
    user.password_hash = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    return user


async def _consume_token(
    db: AsyncSession,
    model: type[EmailVerification] | type[PasswordResetToken],
    token: str,
) -> EmailVerification | PasswordResetToken:
    """校验+消费 token：未过期、未使用，否则 VALIDATION_ERROR。"""
    stmt = select(model).where(model.token_hash == _hash_token(token))
    row = await db.scalar(stmt)
    if row is None or row.used_at is not None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 无效或已用")
    if _utcnow() > _aware(row.expires_at):
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 已过期")
    row.used_at = _utcnow()
    await db.commit()
    return row
