"""进程内 memory 后端：pytest 默认，无需 RabbitMQ 容器。测试使用"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.enums import WSEventType
from app.messaging.tasks import decode_task, encode_task
from app.schemas.ws import WSEvent


class MemoryTaskPublisher:
    """捕获任务供测试断言；不启动 consumer。"""

    captured: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, task: str, payload: dict[str, Any]) -> None:
        """捕获任务到类级列表供测试断言。

        场景：pytest 默认 messaging 后端。
        参数：task - 任务名；payload - 序列化前 dict。
        返回：无。
        """
        MemoryTaskPublisher.captured.append((task, payload))

    @classmethod
    def reset(cls) -> None:
        """清空 captured 任务列表。

        场景：pytest fixture teardown。
        参数：无。
        返回：无。
        """
        cls.captured.clear()


class MemoryWsBus:
    _queues: dict[str, list[asyncio.Queue[str]]] = defaultdict(list)

    async def publish(self, run_id: uuid.UUID, event_type: WSEventType, payload: dict) -> None:
        """向 run 的内存 WS 订阅者广播结构化事件。

        场景：Forge runner 推送进度（memory 模式）。
        参数：run_id、event_type、payload。
        返回：无。
        """
        ev = WSEvent(type=event_type, run_id=run_id, ts=datetime.now(UTC), payload=payload)
        await self.publish_data(run_id, ev.model_dump_json())

    async def publish_data(self, run_id: uuid.UUID, data: str) -> None:
        """向 run 的所有订阅队列推送原始 JSON 字符串。

        场景：publish 序列化后下发。
        参数：run_id、data - WSEvent JSON。
        返回：无。
        """
        for q in list(self._queues.get(str(run_id), [])):
            await q.put(data)

    def subscribe(self, run_id: uuid.UUID) -> asyncio.Queue[str]:
        """为 run 注册新的内存 WS 订阅队列。

        场景：WebSocket 连接建立时。
        参数：run_id。
        返回：asyncio.Queue 供 iter_events 消费。
        """
        q: asyncio.Queue[str] = asyncio.Queue()
        self._queues[str(run_id)].append(q)
        return q

    def unsubscribe(self, run_id: uuid.UUID, q: asyncio.Queue[str]) -> None:
        """移除 run 的某个订阅队列。

        场景：WebSocket 断开时。
        参数：run_id、q - subscribe 返回的队列。
        返回：无。
        """
        rows = self._queues.get(str(run_id), [])
        if q in rows:
            rows.remove(q)

    async def iter_events(self, run_id: uuid.UUID) -> AsyncIterator[str]:
        """异步迭代 run 的 WS 事件直至连接关闭。

        场景：memory 模式 WS handler。
        参数：run_id。
        返回：异步生成器，yield JSON 字符串。
        """
        q = self.subscribe(run_id)
        try:
            while True:
                yield await q.get()
        finally:
            self.unsubscribe(run_id, q)

    @classmethod
    def reset(cls) -> None:
        """清空所有 run 的内存 WS 订阅表。

        场景：pytest teardown。
        参数：无。
        返回：无。
        """
        cls._queues.clear()


async def run_memory_worker(handler) -> None:
    """测试用：同步消费 captured 队列（一般不调用）。"""
    while MemoryTaskPublisher.captured:
        task, payload = MemoryTaskPublisher.captured.pop(0)
        body = encode_task(task, payload)
        t, p = decode_task(body)
        await handler(t, p)
