"""用户反馈 → 管理员邮件。业务薄：限流 → 查 run（归属校验）→ 解析管理员邮箱 → 入队通知邮件。

复用 enqueue_notification（通用通知通道），不新增任务类型；管理员邮箱由
get_admin_contact_email 解析（DB 设置 > 环境变量 > 首个 admin）。
"""

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.services import get_admin_contact_email
from app.auth.ratelimit import check_rate_limit
from app.core.config import settings
from app.email import queue as email_queue
from app.games.services import get_run
from app.models.user import User
from app.schemas.feedback import FeedbackReq, FeedbackResp


async def submit_feedback(
    db: AsyncSession,
    r: Redis,
    user: User,
    ip: str,
    req: FeedbackReq,
) -> FeedbackResp:
    """提交反馈：代发一封邮件给管理员。run 必须属于当前用户。"""
    # 限流：发邮件是可滥用/烧钱操作，按 user+ip 滑动窗口（与 auth 端点同档）。
    await check_rate_limit(
        r, f"rl:feedback:{user.id}:{ip}", settings.default_rate_limit_per_min, 60
    )

    # run 归属校验：不存在或非本人 → GAME_NOT_FOUND（防越权探测他人 run）。
    run = await get_run(db, user, uuid.UUID(req.run_id))

    admin_email = await get_admin_contact_email(db)

    subject = f"GameForge 反馈 · run {run.id}"
    body = _build_body(user, run, req)

    await email_queue.enqueue_notification(admin_email, subject, body)
    return FeedbackResp(submitted=True)


def _build_body(user: User, run: object, req: FeedbackReq) -> str:
    """拼纯文本邮件正文：用户标识 + run 上下文 + 可选错误摘要 + 用户留言。"""
    lines: list[str] = [
        f"用户 ID：{user.id}",
        f"Run ID：{run.id}",
    ]
    phase = getattr(run, "phase", None)
    if phase:
        lines.append(f"失败阶段：{phase}")
    if req.error_summary.strip():
        lines.append("")
        lines.append("【错误摘要】")
        lines.append(req.error_summary.strip())
    if req.message.strip():
        lines.append("")
        lines.append("【用户反馈】")
        lines.append(req.message.strip())
    return "\n".join(lines)
