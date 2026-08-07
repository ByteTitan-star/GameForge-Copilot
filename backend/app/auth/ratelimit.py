"""Redis ZSET 滑动窗口限流。docs/05 §配额与限流。"""

import secrets
import time

import redis.asyncio as redis

from app.core.errors import AppError, ErrorCode


async def check_rate_limit(
    r: redis.Redis, key: str, limit: int, window_s: int
) -> None:
    """超限抛 RATE_LIMITED；member 用随机后缀保证唯一。"""
    now = time.time()
    member = f"{now}:{secrets.token_hex(4)}"
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_s)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_s)
    *_, count, _ = await pipe.execute()
    if count > limit:
        raise AppError(ErrorCode.RATE_LIMITED, "请求过于频繁，稍后再试")
