"""refresh token 在 Redis 的存储 / 轮换 / 撤销。

key: `refresh:{token}` -> user_id（str），TTL = settings.refresh_ttl。
rotation：删旧 token，发新 token（docs/06）。logout：删 token。
"""

import uuid

import redis.asyncio as redis

from app.auth.security import generate_refresh_token
from app.core.config import settings


def _key(token: str) -> str:
    return f"refresh:{token}"


async def issue_refresh(r: redis.Redis, user_id: uuid.UUID) -> str:
    token = generate_refresh_token()
    await r.set(_key(token), str(user_id), ex=settings.refresh_ttl)
    return token


async def verify_refresh(r: redis.Redis, token: str) -> uuid.UUID | None:
    uid = await r.get(_key(token))
    return uuid.UUID(uid) if uid else None


async def rotate_refresh(r: redis.Redis, old_token: str) -> tuple[uuid.UUID, str] | None:
    """轮换：原子 `getdel` 取 user_id 同时删旧 token，杜绝并发双发；再发新 token。"""
    uid = await r.getdel(_key(old_token))
    if uid is None:
        return None
    user_id = uuid.UUID(uid)
    return user_id, await issue_refresh(r, user_id)


async def revoke_refresh(r: redis.Redis, token: str) -> None:
    await r.delete(_key(token))
