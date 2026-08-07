"""鉴权依赖：current_user / require_admin。用 Annotated 避开 ruff B008。"""

import uuid
from typing import Annotated

import jwt
import redis.asyncio as redis
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.services import disabled_user_message
from app.auth.security import decode_access_token
from app.core.db import get_db
from app.core.errors import AppError, ErrorCode
from app.core.redis import get_redis
from app.enums import Role
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)

Creds = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[redis.Redis, Depends(get_redis)]


async def current_user(creds: Creds, db: DbSession) -> User:
    """从 access_token 解析 user_id+role，查 DB 取用户；失败统一 401。"""
    if not creds or not creds.credentials:
        raise AppError(ErrorCode.UNAUTHORIZED, "未登录或 token 失效")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError as e:
        raise AppError(ErrorCode.UNAUTHORIZED, "未登录或 token 失效") from e
    if payload.get("type") != "access":
        raise AppError(ErrorCode.UNAUTHORIZED, "未登录或 token 失效")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as e:
        raise AppError(ErrorCode.UNAUTHORIZED, "未登录或 token 失效") from e
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "未登录或 token 失效")
    if user.disabled:
        raise AppError(ErrorCode.FORBIDDEN, await disabled_user_message(db))
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Role.ADMIN.value:
        raise AppError(ErrorCode.FORBIDDEN, "无权限")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
