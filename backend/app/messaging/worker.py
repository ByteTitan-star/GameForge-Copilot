"""RabbitMQ worker 入口：`uv run python -m app.messaging.worker`。"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.core.config import settings
from app.messaging.handlers import dispatch_task
from app.messaging.rabbit import _task_channel, close_connection
from app.messaging.tasks import TASK_QUEUE, decode_task

log = logging.getLogger(__name__)


async def _scheduler_loop() -> None:
    """每分钟扫描定时下架（B8）。"""
    from app.core import db as dbmod
    from app.scheduler.services import scan_scheduled

    while True:
        await asyncio.sleep(60)
        try:
            async with dbmod.SessionLocal() as s:
                n = await scan_scheduled(s)
                if n:
                    log.info("scheduled take_down count=%s", n)
        except Exception:
            log.exception("scheduler scan failed")


async def _consume() -> None:
    scan_task = asyncio.create_task(_scheduler_loop())
    try:
        channel, _exchange = await _task_channel()
        queue = await channel.declare_queue(TASK_QUEUE, durable=True)
        log.info("worker listening on queue=%s url=%s", TASK_QUEUE, settings.rabbitmq_url)

        async with queue.iterator() as it:
            async for message in it:
                async with message.process(requeue=True):
                    task, payload = decode_task(message.body)
                    log.info("task=%s payload_keys=%s", task, list(payload.keys()))
                    try:
                        await dispatch_task(task, payload)
                    except Exception:
                        log.exception("task=%s failed", task)
                        raise
    finally:
        scan_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scan_task
        await close_connection()


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_consume())


if __name__ == "__main__":
    main()
