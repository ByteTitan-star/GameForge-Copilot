"""RabbitMQ 连接、任务发布、WS topic 发布/订阅。"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from app.core.config import settings
from app.enums import WSEventType
from app.messaging.tasks import (
    TASK_EXCHANGE,
    TASK_EXECUTE_RUN,
    TASK_QUEUE,
    TASK_RESUME_RUN,
    TASK_SEND_NOTIFICATION,
    TASK_SEND_RESET,
    TASK_SEND_VERIFICATION,
    WS_EXCHANGE,
    encode_task,
)
from app.schemas.ws import WSEvent

_connection: AbstractConnection | None = None
_lock = asyncio.Lock()


async def get_connection() -> AbstractConnection:
    global _connection
    if _connection is None or _connection.is_closed:
        async with _lock:
            if _connection is None or _connection.is_closed:
                _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    return _connection


async def close_connection() -> None:
    global _connection
    if _connection is not None and not _connection.is_closed:
        await _connection.close()
    _connection = None


async def _task_channel() -> tuple[AbstractChannel, aio_pika.abc.AbstractExchange]:
    conn = await get_connection()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(TASK_EXCHANGE, ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(TASK_QUEUE, durable=True)
    for rk in (
        TASK_EXECUTE_RUN,
        TASK_RESUME_RUN,
        TASK_SEND_VERIFICATION,
        TASK_SEND_RESET,
        TASK_SEND_NOTIFICATION,
    ):
        await queue.bind(exchange, routing_key=rk)
    return channel, exchange


async def _ws_exchange(channel: AbstractChannel) -> aio_pika.abc.AbstractExchange:
    return await channel.declare_exchange(WS_EXCHANGE, ExchangeType.TOPIC, durable=False)


class RabbitTaskPublisher:
    _exchange: aio_pika.abc.AbstractExchange | None = None
    _channel: AbstractChannel | None = None

    async def _ensure(self) -> aio_pika.abc.AbstractExchange:
        if self._exchange is None:
            self._channel, self._exchange = await _task_channel()
        return self._exchange

    async def publish(self, task: str, payload: dict[str, Any]) -> None:
        exchange = await self._ensure()
        await exchange.publish(
            Message(
                body=encode_task(task, payload),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=task,
        )


class RabbitWsBus:
    async def publish(
        self, run_id: uuid.UUID, event_type: WSEventType, payload: dict
    ) -> None:
        conn = await get_connection()
        channel = await conn.channel()
        try:
            exchange = await _ws_exchange(channel)
            ev = WSEvent(
                type=event_type, run_id=run_id, ts=datetime.now(UTC), payload=payload
            )
            await exchange.publish(
                Message(body=ev.model_dump_json().encode()),
                routing_key=f"run.{run_id}",
            )
        finally:
            await channel.close()

    async def subscribe_queue(self, run_id: uuid.UUID) -> tuple[AbstractChannel, AbstractQueue]:
        conn = await get_connection()
        channel = await conn.channel()
        exchange = await _ws_exchange(channel)
        queue = await channel.declare_queue("", exclusive=True, auto_delete=True)
        await queue.bind(exchange, routing_key=f"run.{run_id}")
        return channel, queue

    async def iter_events(self, run_id: uuid.UUID) -> AsyncIterator[str]:
        channel, queue = await self.subscribe_queue(run_id)
        try:
            async with queue.iterator() as it:
                async for message in it:
                    async with message.process():
                        yield message.body.decode()
        finally:
            await channel.close()


async def ping_rabbitmq() -> bool:
    try:
        conn = await aio_pika.connect_robust(settings.rabbitmq_url)
        await conn.close()
        return True
    except Exception:  # noqa: BLE001 探针
        return False
