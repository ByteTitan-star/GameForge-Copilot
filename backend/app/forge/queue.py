"""run 入队：业务侧调 enqueue_run，RabbitMQ worker 异步消费 execute_run。

测试使用 memory 后端 + monkeypatch no-op。
"""

import uuid

from app.messaging.factory import get_task_publisher
from app.messaging.tasks import (
    TASK_EXECUTE_RUN,
    TASK_RESUME_RUN,
    resume_payload,
    run_id_payload,
)


async def enqueue_run(run_id: uuid.UUID) -> None:
    await get_task_publisher().publish(TASK_EXECUTE_RUN, run_id_payload(run_id))


async def enqueue_resume(
    run_id: uuid.UUID, decision: str, modify_text: str | None
) -> None:
    await get_task_publisher().publish(
        TASK_RESUME_RUN, resume_payload(run_id, decision, modify_text)
    )
