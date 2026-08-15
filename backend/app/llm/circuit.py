"""LLM 熔断器：按 user + provider 隔离爆炸半径（BYOK 场景）。

状态机（Redis）：
- closed：正常；连续失败计数 failures
- open：failures >= 阈值后拒绝新请求，直到 open_until
- half-open：冷却到期后放行一次试探；成功则清零，失败则再次 open

与限流正交：限流防突发，熔断防持续故障空转。
"""

from __future__ import annotations

import time
import uuid
from urllib.parse import urlparse

import redis.asyncio as redis

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import LLMProvider


def circuit_key(
    user_id: uuid.UUID, provider: LLMProvider, base_url: str | None
) -> str:
    host = "default"
    if base_url:
        host = urlparse(base_url).hostname or "default"
    return f"cb:llm:{user_id}:{provider.value}:{host}"


async def assert_circuit_closed(r: redis.Redis, key: str) -> None:
    """熔断打开时拒绝调用。"""
    if not settings.llm_circuit_enabled:
        return
    open_until = await r.hget(key, "open_until")
    if open_until is None:
        return
    try:
        until = float(open_until)
    except (TypeError, ValueError):
        return
    now = time.time()
    if now < until:
        raise AppError(
            ErrorCode.LLM_CIRCUIT_OPEN,
            f"LLM 熔断开启，约 {max(1, int(until - now))} 秒后重试",
        )


async def record_success(r: redis.Redis, key: str) -> None:
    if not settings.llm_circuit_enabled:
        return
    await r.delete(key)


async def record_failure(r: redis.Redis, key: str) -> None:
    if not settings.llm_circuit_enabled:
        return
    failures = int(await r.hincrby(key, "failures", 1))
    ttl = max(settings.llm_circuit_open_s * 2, 120)
    await r.expire(key, ttl)
    if failures < settings.llm_circuit_failure_threshold:
        return
    open_until = time.time() + settings.llm_circuit_open_s
    await r.hset(key, mapping={"open_until": str(open_until), "failures": str(failures)})
    await r.expire(key, ttl)
