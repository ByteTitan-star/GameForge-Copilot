"""任务分发：consumer 收到消息后路由到 email / forge handler。"""

from __future__ import annotations

import uuid

import redis.asyncio as redis

from app.core.config import settings
from app.email.worker import (
    send_notification_email,
    send_reset_email,
    send_verification_email,
)
from app.forge.runner import execute_run, resume_run
from app.messaging.tasks import (
    TASK_EXECUTE_RUN,
    TASK_RESUME_RUN,
    TASK_SEND_NOTIFICATION,
    TASK_SEND_RESET,
    TASK_SEND_VERIFICATION,
)

_redis: redis.Redis | None = None


def _worker_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def worker_ctx() -> dict:
    return {"redis": _worker_redis()}


async def dispatch_task(task: str, payload: dict) -> None:
    ctx = worker_ctx()
    match task:
        case _ if task == TASK_SEND_VERIFICATION:
            await send_verification_email(ctx, payload["email"], payload["code"])
        case _ if task == TASK_SEND_RESET:
            await send_reset_email(ctx, payload["email"], payload["token"])
        case _ if task == TASK_SEND_NOTIFICATION:
            await send_notification_email(
                ctx, payload["email"], payload["subject"], payload["body"]
            )
        case _ if task == TASK_EXECUTE_RUN:
            await execute_run(ctx, uuid.UUID(payload["run_id"]))
        case _ if task == TASK_RESUME_RUN:
            await resume_run(
                ctx,
                uuid.UUID(payload["run_id"]),
                payload["decision"],
                payload.get("modify_text"),
            )
        case _:
            raise ValueError(f"unknown task: {task}")
