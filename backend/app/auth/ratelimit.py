"""Redis ZSET 滑动窗口限流。docs/05 §配额与限流。"""

import secrets
import time

import redis.asyncio as redis

from app.core.errors import AppError, ErrorCode


async def check_rate_limit(r: redis.Redis, key: str, limit: int, window_s: int) -> None:
    """滑动窗口限流检查。

    作用：ZSET 记录请求时间戳，窗口内超过 limit 抛 RATE_LIMITED。
    场景：注册/登录/验证码/LLM 探测等按 IP 或用户限流。
    参数：r — Redis；key — 限流桶键；limit — 窗口内最大次数；window_s — 窗口秒数。
    返回：无；超限时抛 AppError(RATE_LIMITED)。
    """
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
