"""邮件发送任务（RabbitMQ worker 内执行）。SMTP 缺失时控制台打印（dev）。"""

from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

import aiosmtplib

from app.core.config import settings


def _smtp_tls_kwargs() -> dict[str, bool]:
    """根据 SMTP 端口选择 TLS 连接方式。

    作用：465 用隐式 SSL（use_tls）；587/25 用 STARTTLS。
    场景：_send 构造 aiosmtplib.send 参数。
    参数：无（读取 settings.smtp_port）。
    返回：含 use_tls 或 start_tls 的 kwargs 字典。
    """
    if settings.smtp_port == 465:
        return {"use_tls": True}
    return {"start_tls": True}


def _format_from_header() -> str:
    """构造 SMTP 发件人 From 头。

    作用：组合显示名与邮箱，如 GameForge <noreply@example.com>。
    场景：_send 设置 EmailMessage From 字段。
    参数：无（读取 settings.smtp_from、smtp_user、smtp_from_name）。
    返回：RFC 5322 格式发件人字符串。
    """
    addr = settings.smtp_from or settings.smtp_user
    name = settings.smtp_from_name.strip()
    if name and addr:
        return formataddr((name, addr))
    return addr


async def _send(email: str, subject: str, body: str) -> None:
    """发送单封邮件（SMTP 或 dev 控制台回退）。

    作用：smtp_host 未配置时打印到控制台；否则经 aiosmtplib 发送。
    场景：各类 send_*_email worker 任务的内层发送。
    参数：email — 收件人；subject — 主题；body — 纯文本正文。
    返回：无；SMTP 失败显式抛错供 broker 重投。
    """
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
    """生成密码重置前端链接。

    作用：拼接 frontend_base_url 与 reset token 查询参数。
    场景：send_reset_email 正文内嵌链接。
    参数：token — 重置令牌。
    返回：完整 URL 字符串。
    """
    return f"{settings.frontend_base_url}/reset-password?token={token}"


async def send_verification_email(ctx: dict, email: str, code: str) -> None:
    """发送邮箱验证码邮件。

    作用：将 6 位验证码与验证页链接发给用户。
    场景：TASK_SEND_VERIFICATION worker 任务消费。
    参数：ctx — 任务上下文（未使用）；email — 收件人；code — 验证码。
    返回：无。
    """
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
    """发送密码重置链接邮件。

    作用：将带 token 的重置链接发给用户（1 小时有效）。
    场景：TASK_SEND_RESET worker 任务消费。
    参数：ctx — 任务上下文（未使用）；email — 收件人；token — 重置令牌。
    返回：无。
    """
    _ = ctx
    body = f"点击链接重置密码（1 小时内有效）：\n{_reset_link(token)}"
    await _send(email, "重置你的 GameForge 密码", body)


async def send_notification_email(ctx: dict, email: str, subject: str, body: str) -> None:
    """发送通用通知邮件。

    作用：审批结果、下架、配额告警等业务通知的邮件通道。
    场景：TASK_SEND_NOTIFICATION worker 任务消费。
    参数：ctx — 任务上下文（未使用）；email — 收件人；subject/body — 主题与正文。
    返回：无。
    """
    _ = ctx
    await _send(email, subject, body)
