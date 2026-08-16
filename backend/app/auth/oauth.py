"""OAuth 登录（B7）：GitHub / Google。"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.auth.services import issue_session
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import Role
from app.models.oauth_account import OAuthAccount
from app.models.user import User

_PROVIDERS = {"github", "google"}


@dataclass
class OAuthProfile:
    provider_sub: str
    email: str
    name: str | None = None


async def oauth_start(r: redis.Redis, provider: str) -> dict[str, str]:
    if provider not in _PROVIDERS:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的 OAuth 提供商")
    state = secrets.token_urlsafe(24)
    await r.set(f"oauth:state:{state}", provider, ex=600)
    if provider == "github":
        if not settings.oauth_github_client_id:
            raise AppError(ErrorCode.VALIDATION_ERROR, "GitHub OAuth 未配置")
        q = urlencode(
            {
                "client_id": settings.oauth_github_client_id,
                "redirect_uri": _callback_url("github"),
                "scope": "read:user user:email",
                "state": state,
            }
        )
        return {"redirect_url": f"https://github.com/login/oauth/authorize?{q}", "state": state}
    if not settings.oauth_google_client_id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Google OAuth 未配置")
    q = urlencode(
        {
            "client_id": settings.oauth_google_client_id,
            "redirect_uri": _callback_url("google"),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
    )
    return {"redirect_url": f"https://accounts.google.com/o/oauth2/v2/auth?{q}", "state": state}


def _callback_url(provider: str) -> str:
    return f"{settings.api_public_url.rstrip('/')}/api/v1/auth/oauth/{provider}/callback"


async def fetch_oauth_profile(provider: str, code: str) -> OAuthProfile:
    """交换 code 并拉取用户信息（测试 monkeypatch 此函数）。"""
    if provider == "github":
        return await _github_profile(code)
    return await _google_profile(code)


async def _github_profile(code: str) -> OAuthProfile:
    async with httpx.AsyncClient(timeout=15) as client:
        tok = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.oauth_github_client_id,
                "client_secret": settings.oauth_github_client_secret,
                "code": code,
                "redirect_uri": _callback_url("github"),
            },
        )
        tok.raise_for_status()
        access = tok.json().get("access_token")
        if not access:
            raise AppError(ErrorCode.UNAUTHORIZED, "OAuth token 交换失败")
        me = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access}"},
        )
        me.raise_for_status()
        data = me.json()
        email = data.get("email") or f"{data['id']}@users.noreply.github.com"
        return OAuthProfile(provider_sub=str(data["id"]), email=email, name=data.get("login"))


async def _google_profile(code: str) -> OAuthProfile:
    async with httpx.AsyncClient(timeout=15) as client:
        tok = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.oauth_google_client_id,
                "client_secret": settings.oauth_google_client_secret,
                "redirect_uri": _callback_url("google"),
                "grant_type": "authorization_code",
            },
        )
        tok.raise_for_status()
        access = tok.json().get("access_token")
        if not access:
            raise AppError(ErrorCode.UNAUTHORIZED, "OAuth token 交换失败")
        info = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access}"},
        )
        info.raise_for_status()
        data = info.json()
        return OAuthProfile(
            provider_sub=str(data["sub"]), email=str(data["email"]), name=data.get("name")
        )


async def oauth_callback(
    db: AsyncSession,
    r: redis.Redis,
    provider: str,
    code: str,
    state: str,
) -> tuple[User, str, str]:
    saved = await r.getdel(f"oauth:state:{state}")
    if saved != provider:
        raise AppError(ErrorCode.UNAUTHORIZED, "OAuth state 无效")
    profile = await fetch_oauth_profile(provider, code)
    link = await db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_sub == profile.provider_sub,
        )
    )
    if link is not None:
        user = await db.get(User, link.user_id)
        if user is None:
            raise AppError(ErrorCode.UNAUTHORIZED, "OAuth 账号无效")
        return await issue_session(db, r, user)

    existing = await db.scalar(select(User).where(User.email == profile.email))
    if existing is not None:
        if not existing.email_verified:
            raise AppError(
                ErrorCode.EMAIL_NOT_VERIFIED,
                "该邮箱已注册但未验证，请先完成邮箱验证后再关联 OAuth",
            )
        db.add(
            OAuthAccount(
                user_id=existing.id,
                provider=provider,
                provider_sub=profile.provider_sub,
                email=profile.email,
            )
        )
        await db.commit()
        await db.refresh(existing)
        return await issue_session(db, r, existing)

    user = User(
        email=profile.email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=Role.USER.value,
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    db.add(
        OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_sub=profile.provider_sub,
            email=profile.email,
        )
    )
    await db.commit()
    await db.refresh(user)
    return await issue_session(db, r, user)
