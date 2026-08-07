"""邮件入队：业务侧调 enqueue_*，RabbitMQ worker 异步消费。

测试 monkeypatch enqueue_* 为 capture，不依赖真实 broker。
"""

from app.core.config import settings
from app.messaging.factory import get_task_publisher
from app.messaging.tasks import (
    TASK_SEND_NOTIFICATION,
    TASK_SEND_RESET,
    TASK_SEND_VERIFICATION,
)


async def enqueue_verification(email: str, code: str) -> None:
    await get_task_publisher().publish(
        TASK_SEND_VERIFICATION, {"email": email, "code": code}
    )
    if settings.env == "development":
        import redis.asyncio as redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.setex(
                f"dev:verify:{email.strip().lower()}",
                settings.verify_email_ttl,
                code,
            )
        finally:
            await client.aclose()


async def enqueue_reset(email: str, token: str) -> None:
    await get_task_publisher().publish(TASK_SEND_RESET, {"email": email, "token": token})


async def enqueue_notification(email: str, subject: str, body: str) -> None:
    """审批/下架/配额告警等通知邮件（docs/04 §通知）。"""
    await get_task_publisher().publish(
        TASK_SEND_NOTIFICATION, {"email": email, "subject": subject, "body": body}
    )
