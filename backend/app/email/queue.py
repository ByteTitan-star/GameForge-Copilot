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
    """将邮箱验证码发送任务入队。

    作用：发布 TASK_SEND_VERIFICATION；dev 环境额外写入 Redis dev:verify 键。
    场景：用户注册或重发验证码流程。
    参数：email — 目标邮箱；code — 6 位验证码。
    返回：无。
    """
    await get_task_publisher().publish(TASK_SEND_VERIFICATION, {"email": email, "code": code})
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
    """将密码重置邮件任务入队。

    作用：发布 TASK_SEND_RESET 到消息队列。
    场景：用户申请重置密码流程。
    参数：email — 目标邮箱；token — 重置令牌。
    返回：无。
    """
    await get_task_publisher().publish(TASK_SEND_RESET, {"email": email, "token": token})


async def enqueue_notification(email: str, subject: str, body: str) -> None:
    """将通用通知邮件任务入队。

    作用：发布 TASK_SEND_NOTIFICATION（审批/下架/配额告警等）。
    场景：notify_user、submit_feedback 等业务侧发信。
    参数：email — 收件人；subject — 主题；body — 正文。
    返回：无。
    """
    await get_task_publisher().publish(
        TASK_SEND_NOTIFICATION, {"email": email, "subject": subject, "body": body}
    )
