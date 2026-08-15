"""run 入队：业务侧调 enqueue_run / enqueue_resume，RabbitMQ worker 异步消费。

enqueue_resume 会先向 checkpoint 写入一次性「推进凭据」resume_grant，再入队
resume_run：worker 执行入口校验该凭据，命中即消费并清除；缺失则视为陈旧消息
（at-least-once 重投）直接跳过，从而堵住 HITL 等待期间被旧消息擅自推进。

测试使用 memory 后端 + monkeypatch no-op。
"""

import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.forge import state as ckpt
from app.messaging.factory import get_task_publisher
from app.messaging.outbox import add_task
from app.messaging.tasks import (
    TASK_EXECUTE_RUN,
    TASK_RESUME_RUN,
    resume_payload,
    run_id_payload,
)


async def enqueue_run(run_id: uuid.UUID) -> None:
    await get_task_publisher().publish(TASK_EXECUTE_RUN, run_id_payload(run_id))


async def enqueue_resume(
    db: AsyncSession,
    r: redis.Redis,
    run_id: uuid.UUID,
    decision: str,
    modify_text: str | None,
) -> None:
    """写 resume_grant 凭据 + 入队 resume_run，二者在同一 db 事务内提交。

    必须由所有合法的 resume_run 入队点调用（resolve_hitl / resume_run_control /
    retry_run / dev_requeue），避免某条路径漏写凭据导致 worker 把它当成陈旧消息跳过。
    """
    st = await ckpt.load_state(r, run_id, db) or {}
    granted = {**st, "resume_grant": {"decision": decision, "modify_text": modify_text}}
    await ckpt.save_state(r, run_id, granted, db)
    await add_task(db, TASK_RESUME_RUN, resume_payload(run_id, decision, modify_text))
