"""邮件发送任务（RabbitMQ worker 内执行）。SMTP 缺失时控制台打印（dev）。"""

from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

import aiosmtplib

from app.core.config import settings


def _smtp_tls_kwargs() -> dict[str, bool]:
    """465=隐式 SSL；587/25=明文连接后 STARTTLS（163 推荐 465）。"""
    if settings.smtp_port == 465:
        return {"use_tls": True}
    return {"start_tls": True}


def _format_from_header() -> str:
    """发件人显示名 + 邮箱，如 GameForge <noreply@example.com>。"""
    addr = settings.smtp_from or settings.smtp_user
    name = settings.smtp_from_name.strip()
    if name and addr:
        return formataddr((name, addr))
    return addr


async def _send(email: str, subject: str, body: str) -> None:
    """SMTP 配置缺失则控制台打印；失败显式抛错，由 broker 重投，不静默吞。"""
    if not settings.smtp_host:
        print(f"[dev-email] to={email} | subject={subject}\n{body}")  # noqa: T201
        return
    msg = EmailMessage()
    msg["From"] = _format_from_header()
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(body)
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_pass or None,
        **_smtp_tls_kwargs(),
    )


def _reset_link(token: str) -> str:
    return f"{settings.frontend_base_url}/reset-password?token={token}"


async def send_verification_email(ctx: dict, email: str, code: str) -> None:
    _ = ctx
    ttl_min = max(1, settings.verify_email_ttl // 60)
    body = (
        f"您的 GameForge 邮箱验证码：{code}\n\n"
        f"请在 {ttl_min} 分钟内于验证页输入此 6 位数字完成验证。\n"
        f"验证页：{settings.frontend_base_url}/verify-email?email={quote(email)}\n\n"
        f"如非本人操作，请忽略此邮件。"
    )
    await _send(email, "GameForge 邮箱验证码", body)


async def send_reset_email(ctx: dict, email: str, token: str) -> None:
    _ = ctx
    body = f"点击链接重置密码（1 小时内有效）：\n{_reset_link(token)}"
    await _send(email, "重置你的 GameForge 密码", body)


async def send_notification_email(ctx: dict, email: str, subject: str, body: str) -> None:
    """通用通知（审批结果/下架/配额告警）。"""
    _ = ctx
    await _send(email, subject, body)
