"""refresh token 在 Redis 的存储 / 轮换 / 撤销。

key: `refresh:{token}` -> user_id（str），TTL = settings.refresh_ttl。
rotation：删旧 token，发新 token（docs/06）。logout：删 token。
"""

import uuid

import redis.asyncio as redis

from app.auth.security import generate_refresh_token
from app.core.config import settings


def _key(token: str) -> str:
    """构造 refresh token 的 Redis 键名。

    作用：统一 refresh:{token} 前缀。
    场景：issue/verify/rotate/revoke 内部使用。
    参数：token — opaque refresh 字符串。
    返回：Redis 键字符串。
    """
    return f"refresh:{token}"


async def issue_refresh(r: redis.Redis, user_id: uuid.UUID) -> str:
    """签发新 refresh token 并写入 Redis。

    作用：生成随机 token，SET refresh:{token}=user_id 并设 TTL。
    场景：登录、OAuth 回调、refresh 轮换后。
    参数：r — Redis 客户端；user_id — 所属用户。
    返回：新 refresh token 字符串。
    """
    token = generate_refresh_token()
    await r.set(_key(token), str(user_id), ex=settings.refresh_ttl)
    return token


async def verify_refresh(r: redis.Redis, token: str) -> uuid.UUID | None:
    """校验 refresh token 是否有效。

    作用：GET refresh:{token} 解析 user_id。
    场景：仅验证不落库的场景（本仓库主要用 rotate）。
    参数：r — Redis；token — refresh 字符串。
    返回：user_id；无效或过期返回 None。
    """
    uid = await r.get(_key(token))
    return uuid.UUID(uid) if uid else None


async def rotate_refresh(r: redis.Redis, old_token: str) -> tuple[uuid.UUID, str] | None:
    """轮换 refresh token（原子 getdel + 新发）。

    作用：getdel 旧键取 user_id 并删除，再 issue 新 token，防并发双发。
    场景：POST /auth/refresh 刷新会话。
    参数：r — Redis；old_token — 客户端持有的旧 refresh。
    返回：(user_id, new_token) 或 None（旧 token 无效）。
    """
    uid = await r.getdel(_key(old_token))
    if uid is None:
        return None
    user_id = uuid.UUID(uid)
    return user_id, await issue_refresh(r, user_id)


async def revoke_refresh(r: redis.Redis, token: str) -> None:
    """撤销 refresh token。

    作用：DELETE refresh:{token}。
    场景：用户登出。
    参数：r — Redis；token — 待撤销的 refresh 字符串。
    返回：无。
    """
    await r.delete(_key(token))
