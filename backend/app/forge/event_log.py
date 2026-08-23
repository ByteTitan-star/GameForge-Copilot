"""Run WS 事件环形缓冲（Redis），支持刷新/重连后 replay。"""

from __future__ import annotations

import json
import uuid
from contextvars import ContextVar

import redis.asyncio as redis

from app.core.redis import pool

_KEY = "run:events:{run_id}"
_SEQ_KEY = "run:event_seq:{run_id}"
_MAX_EVENTS = 200
_TTL_SECONDS = 86400 * 7

_event_redis: ContextVar[redis.Redis | None] = ContextVar("_event_redis", default=None)


def bind_event_redis(client: redis.Redis | None) -> None:
    """注入与请求/worker 共享的 Redis 客户端到上下文变量。

    场景：worker ``execute_run`` / 测试夹具绑定 Redis，避免每次新建连接。
    参数：client - Redis 客户端或 None（回退连接池）。
    返回：无。
    """
    _event_redis.set(client)


async def _client() -> tuple[redis.Redis, bool]:
    """获取事件日志用的 Redis 客户端。

    场景：``publish_event`` / ``list_events_auto`` 内部获取连接。
    参数：无。
    返回：(client, owned) 元组；owned 为 True 时调用方需 aclose。
    """
    bound = _event_redis.get()
    if bound is not None:
        return bound, False
    return redis.Redis(connection_pool=pool), True


async def append_event(r: redis.Redis, run_id: uuid.UUID, data: str) -> None:
    """将序列化事件追加到 Redis 环形列表并维护 TTL。

    场景：``publish_event`` 写入缓冲供刷新后 replay。
    参数：r - Redis 客户端；run_id - 生成任务 ID；data - JSON 序列化的事件文本。
    返回：无；列表超 _MAX_EVENTS 时自动 ltrim。
    """
    key = _KEY.format(run_id=run_id)
    async with r.pipeline(transaction=True) as pipe:
        pipe.rpush(key, data)
        pipe.ltrim(key, -_MAX_EVENTS, -1)
        pipe.expire(key, _TTL_SECONDS)
        await pipe.execute()


async def next_event_seq(r: redis.Redis, run_id: uuid.UUID) -> int:
    """原子递增并返回 run 的下一个事件序号。

    场景：``publish_event`` 为 WSEvent 分配单调递增 seq。
    参数：r - Redis 客户端；run_id - 生成任务 ID。
    返回：新序号（从 1 起）。
    """
    key = _SEQ_KEY.format(run_id=run_id)
    async with r.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, _TTL_SECONDS)
        values = await pipe.execute()
    return int(values[0])


async def list_events(r: redis.Redis, run_id: uuid.UUID, after: int | None = None) -> list[str]:
    """从 Redis 环形缓冲读取事件，可按 seq 过滤。

    场景：WebSocket replay 端点；断线重连补发。
    参数：r - Redis 客户端；run_id - 生成任务 ID；after - 可选，仅返回 seq > after 的事件。
    返回：JSON 序列化事件字符串列表。
    """
    key = _KEY.format(run_id=run_id)
    rows = await r.lrange(key, 0, -1)
    events = list(rows or [])
    if not after:
        return events
    filtered: list[str] = []
    for line in events:
        try:
            seq = json.loads(line).get("seq")
        except (json.JSONDecodeError, AttributeError):
            seq = None
        if seq is None or int(seq) > after:
            filtered.append(line)
    return filtered


async def list_events_auto(run_id: uuid.UUID, after: int | None = None) -> list[str]:
    """自动获取 Redis 客户端并列出事件（调用方无需传 client）。

    场景：API 层 replay 端点；无 worker 上下文时使用连接池。
    参数：run_id - 生成任务 ID；after - 可选 seq 过滤下界。
    返回：JSON 序列化事件字符串列表。
    """
    client, owned = await _client()
    try:
        return await list_events(client, run_id, after)
    finally:
        if owned:
            await client.aclose()


async def clear_events(r: redis.Redis, run_id: uuid.UUID) -> None:
    """删除 run 的事件缓冲与序号键。

    场景：run 结束清理或测试 teardown。
    参数：r - Redis 客户端；run_id - 生成任务 ID。
    返回：无。
    """
    await r.delete(_KEY.format(run_id=run_id), _SEQ_KEY.format(run_id=run_id))
