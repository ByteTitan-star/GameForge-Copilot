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
from app.auth.trial import is_trial_user, reject_trial_mutation
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
    """返回当前 UTC 时间（timezone-aware）。

    场景：验证码/ token 过期判断。
    参数：无。
    返回：datetime 对象。
    """
    """返回当前 UTC 时间（aware）。

    作用：统一业务层时间戳来源。
    场景：验证码/ token 过期判断。
    参数：无。
    返回：timezone-aware datetime。
    """
    return datetime.now(UTC)


def _gen_verification_code() -> str:
    """6 位数字验证码（000000–999999，首位可为 0）。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def _gen_token() -> str:
    """密码重置等高熵链接 token。"""
    return secrets.token_urlsafe(32)


async def _invalidate_pending_verifications(db: AsyncSession, user_id: uuid.UUID) -> None:
    """作废用户所有未使用的邮箱验证码记录。

    场景：重发验证码前、爆破达限后。
    参数：db、user_id。
    返回：无；有记录时 commit。
    """
    """作废用户全部未使用的邮箱验证码。

    作用：将 pending 验证码标记为已用。
    场景：重发验证码前清理旧记录。
    参数：db — 会话；user_id — 用户 ID。
    返回：无。
    """
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
    """生成并持久化 6 位邮箱验证码。

    场景：register_user、resend_verification。
    参数：db、user_id。
    返回：明文验证码（由调用方发邮件）。
    """
    """生成并持久化新的邮箱验证码。

    作用：写入 EmailVerification 行并提交。
    场景：注册、重发验证邮件。
    参数：db — 会话；user_id — 用户 ID。
    返回：6 位验证码明文（供发邮件）。
    """
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


async def register_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    """创建未验证用户并发 6 位邮箱验证码；返回 (user, code)，由调用方入队发邮件。"""
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=Role.USER.value,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise AppError(ErrorCode.EMAIL_TAKEN, "邮箱已注册") from e
    await db.refresh(user)
    code = await _issue_verification_code(db, user.id)
    return user, code


async def resend_verification(db: AsyncSession, email: str) -> str | None:
    """未验证用户重发验证码；已验证/不存在返回 None（防枚举）。"""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or user.email_verified:
        return None
    await _invalidate_pending_verifications(db, user.id)
    return await _issue_verification_code(db, user.id)


async def invalidate_pending_verifications_for_email(db: AsyncSession, email: str) -> None:
    """作废某邮箱用户全部未使用验证码（爆破达限后调用）。"""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        return
    await _invalidate_pending_verifications(db, user.id)


async def verify_email(db: AsyncSession, email: str, code: str) -> User:
    """校验邮箱验证码并标记 email_verified。

    场景：POST /auth/verify-email。
    参数：db、email、6 位 code。
    返回：已验证 User；无效/过期抛 VALIDATION_ERROR。
    """
    """校验邮箱验证码并标记用户已验证。

    作用：匹配未过期、未使用的验证码后更新 user.email_verified。
    场景：POST /auth/verify-email。
    参数：db — 会话；email — 邮箱；code — 6 位验证码。
    返回：已验证的 User ORM 实例。
    """
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
    """邮箱密码登录并签发 access/refresh token。

    场景：POST /auth/login。
    参数：db、redis、email、password。
    返回：(user, access_token, refresh_token)。
    """
    """邮箱密码登录并签发会话。

    作用：校验凭据后调用 issue_session。
    场景：POST /auth/login。
    参数：db — 会话；r — Redis；email/password — 登录凭据。
    返回：(User, access_token, refresh_token)。
    """
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(ErrorCode.UNAUTHORIZED, "邮箱或密码错误")
    return await issue_session(db, r, user)


async def issue_session(db: AsyncSession, r: redis.Redis, user: User) -> tuple[User, str, str]:
    """为已认证用户签发会话 token（禁用账号抛 FORBIDDEN）。

    场景：login_user、OAuth callback。
    参数：db、redis、user。
    返回：(user, access, refresh)。
    """
    """为已认证用户签发 access 与 refresh token。

    作用：检查账号未禁用后生成 JWT 与 Redis refresh。
    场景：登录、OAuth 回调成功后。
    参数：db — 会话；r — Redis；user — 用户 ORM。
    返回：(User, access_token, refresh_token)。
    """
    if user.disabled:
        raise AppError(ErrorCode.FORBIDDEN, await disabled_user_message(db))
    access = create_access_token(user_id=user.id, role=user.role)
    refresh = await issue_refresh(r, user.id)
    return user, access, refresh


async def refresh_tokens(db: AsyncSession, r: redis.Redis, refresh_token: str) -> tuple[str, str]:
    """旋转 refresh token 并签发新 access token。

    场景：POST /auth/refresh。
    参数：db、redis、旧 refresh_token。
    返回：(新 access, 新 refresh)。
    """
    """轮换 refresh token 并签发新 access token。

    作用：rotate_refresh 后重新生成 JWT。
    场景：POST /auth/refresh。
    参数：db — 会话；r — Redis；refresh_token — 旧 refresh 字符串。
    返回：(new_access_token, new_refresh_token)。
    """
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
    """撤销 refresh token（登出）。

    场景：POST /auth/logout。
    参数：redis、refresh_token。
    返回：无。
    """
    """登出：撤销 refresh token。

    作用：从 Redis 删除 refresh:{token}。
    场景：POST /auth/logout。
    参数：r — Redis；refresh_token — 待撤销 token。
    返回：无。
    """
    await revoke_refresh(r, refresh_token)


async def request_password_reset(db: AsyncSession, email: str) -> tuple[str, str] | None:
    """防枚举：用户不存在时返回 None，调用方仍恒返回 sent=true。"""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or is_trial_user(user):
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


async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> User:
    """消费重置 token 并设置新密码。

    作用：校验 token 后更新 password_hash。
    场景：POST /auth/password/reset/confirm。
    参数：db — 会话；token — 重置链接 token；new_password — 新密码。
    返回：更新后的 User ORM 实例。
    """
    row = await _consume_token(db, PasswordResetToken, token)
    user = await db.get(User, row.user_id)
    if user is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 无效")
    reject_trial_mutation(user)
    user.password_hash = hash_password(new_password)
    await db.commit()
    return user


async def change_password(
    user: User, db: AsyncSession, old_password: str, new_password: str
) -> User:
    """登录态改密：旧密码错误 → 401；成功写新 hash。"""
    reject_trial_mutation(user)
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
    if not isinstance(row, (EmailVerification, PasswordResetToken)):
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 无效或已用")
    if row.used_at is not None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 无效或已用")
    if _utcnow() > _aware(row.expires_at):
        raise AppError(ErrorCode.VALIDATION_ERROR, "token 已过期")
    row.used_at = _utcnow()
    await db.commit()
    return row
