"""进程内 memory 后端：pytest 默认，无需 RabbitMQ 容器。"""

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
        MemoryTaskPublisher.captured.append((task, payload))

    @classmethod
    def reset(cls) -> None:
        cls.captured.clear()


class MemoryWsBus:
    _queues: dict[str, list[asyncio.Queue[str]]] = defaultdict(list)

    async def publish(
        self, run_id: uuid.UUID, event_type: WSEventType, payload: dict
    ) -> None:
        ev = WSEvent(
            type=event_type, run_id=run_id, ts=datetime.now(UTC), payload=payload
        )
        data = ev.model_dump_json()
        for q in list(self._queues.get(str(run_id), [])):
            await q.put(data)

    def subscribe(self, run_id: uuid.UUID) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._queues[str(run_id)].append(q)
        return q

    def unsubscribe(self, run_id: uuid.UUID, q: asyncio.Queue[str]) -> None:
        rows = self._queues.get(str(run_id), [])
        if q in rows:
            rows.remove(q)

    async def iter_events(self, run_id: uuid.UUID) -> AsyncIterator[str]:
        q = self.subscribe(run_id)
        try:
            while True:
                yield await q.get()
        finally:
            self.unsubscribe(run_id, q)

    @classmethod
    def reset(cls) -> None:
        cls._queues.clear()


async def run_memory_worker(handler) -> None:
    """测试用：同步消费 captured 队列（一般不调用）。"""
    while MemoryTaskPublisher.captured:
        task, payload = MemoryTaskPublisher.captured.pop(0)
        body = encode_task(task, payload)
        t, p = decode_task(body)
        await handler(t, p)
