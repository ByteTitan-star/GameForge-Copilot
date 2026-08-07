"""RabbitMQ worker 入口：`uv run python -m app.messaging.worker`。"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.messaging.handlers import dispatch_task
from app.messaging.rabbit import _task_channel, close_connection
from app.messaging.tasks import TASK_QUEUE, decode_task

log = logging.getLogger(__name__)


async def _consume() -> None:
    channel, _exchange = await _task_channel()
    queue = await channel.declare_queue(TASK_QUEUE, durable=True)
    log.info("worker listening on queue=%s url=%s", TASK_QUEUE, settings.rabbitmq_url)

    async with queue.iterator() as it:
        async for message in it:
            async with message.process(requeue=True):
                task, payload = decode_task(message.body)
                log.info("task=%s payload_keys=%s", task, list(payload.keys()))
                await dispatch_task(task, payload)


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    try:
        asyncio.run(_consume())
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(close_connection())


if __name__ == "__main__":
    main()
