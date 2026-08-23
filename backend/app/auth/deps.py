"""鉴权依赖：current_user / require_admin。用 Annotated 避开 ruff B008。"""

import uuid
from typing import Annotated

import jwt
import redis.asyncio as redis
from fastapi import Depends
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
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
    """从 Authorization 凭证解析 access JWT 并加载当前用户。

    作用：解码 JWT、查 DB 取 User、校验未禁用。
    场景：FastAPI Depends(CurrentUser) 保护需登录路由。
    参数：creds — Authorization 头凭证；db — 数据库会话。
    返回：User ORM 实例；缺失/无效 token 或用户禁用则 401/403。
    """
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
    """校验当前用户为管理员角色。

    作用：role 非 ADMIN 时拒绝访问。
    场景：Depends(AdminUser) 保护 /admin 路由。
    参数：user — 已通过 current_user 校验的用户。
    返回：同一 User 实例；非管理员 403。
    """
    if user.role != Role.ADMIN.value:
        raise AppError(ErrorCode.FORBIDDEN, "无权限")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
