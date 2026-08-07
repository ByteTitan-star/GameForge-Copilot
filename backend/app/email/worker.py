"""邮件发送任务（RabbitMQ worker 内执行）。SMTP 缺失时控制台打印（dev）。"""

from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings


async def _send(email: str, subject: str, body: str) -> None:
    """SMTP 配置缺失则控制台打印；失败显式抛错，由 broker 重投，不静默吞。"""
    if not settings.smtp_host:
        print(f"[dev-email] to={email} | subject={subject}\n{body}")  # noqa: T201
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(body)
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_pass or None,
        start_tls=True,
    )


def _verify_link(token: str) -> str:
    return f"{settings.frontend_base_url}/verify-email?token={token}"


def _reset_link(token: str) -> str:
    return f"{settings.frontend_base_url}/reset-password?token={token}"


async def send_verification_email(ctx: dict, email: str, token: str) -> None:
    _ = ctx
    body = f"点击链接完成验证：\n{_verify_link(token)}"
    await _send(email, "验证你的 GameForge 邮箱", body)


async def send_reset_email(ctx: dict, email: str, token: str) -> None:
    _ = ctx
    body = f"点击链接重置密码（1 小时内有效）：\n{_reset_link(token)}"
    await _send(email, "重置你的 GameForge 密码", body)


async def send_notification_email(ctx: dict, email: str, subject: str, body: str) -> None:
    """通用通知（审批结果/下架/配额告警）。"""
    _ = ctx
    await _send(email, subject, body)
