from collections.abc import AsyncIterator

import redis.asyncio as redis

from app.core.config import settings

pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=settings.redis_socket_connect_timeout,
    socket_timeout=settings.redis_socket_timeout,
)


async def get_redis() -> AsyncIterator[redis.Redis]:
    """请求级 Redis 客户端依赖注入。

    作用：从连接池创建 Redis 客户端并在请求结束后关闭。
    场景：FastAPI 路由通过 Depends(get_redis) 获取 Redis 连接。
    参数：无。
    返回：异步生成器，产出 redis.Redis 实例。
    """
    client = redis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()
