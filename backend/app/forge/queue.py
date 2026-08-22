"""run 入队：业务侧调 enqueue_run / enqueue_resume，RabbitMQ worker 异步消费。

enqueue_resume 是 Resume 公共边界：规范化 legacy decision、写入 RunCommand、
CAS control_revision、写入一次性 resume_grant，再入队 resume_run。
"""

import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import RunCommandType
from app.forge import state as ckpt
from app.forge.commands import (
    bump_control_revision,
    insert_run_command,
    legacy_decision_for,
    normalize_resume_command,
)
from app.forge.hitl import is_cross_stage_replan_phase
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
    *,
    source: str = "hitl",
    expected_control_revision: int | None = None,
    command: str | None = None,
) -> uuid.UUID:
    """写 RunCommand + resume_grant + 入队 resume_run，同一 db 事务。

    必须由所有合法的 resume_run 入队点调用（resolve_hitl / resume_run_control /
    retry_run / dev_requeue）。
    """
    st = await ckpt.load_state(r, run_id, db) or {}
    from app.forge.checkpoint_slim import hydrate_checkpoint_payloads

    st = await hydrate_checkpoint_payloads(db, st)
    phase = str(st.get("phase") or "")
    mapped = normalize_resume_command(
        phase=phase,
        decision=decision,
        pause_reason=str(st["pause_reason"]) if st.get("pause_reason") else None,
        source=source,
        feedback=modify_text,
        command=command,
    )
    decision_key = decision or legacy_decision_for(mapped.command_type)
    if mapped.command_type is RunCommandType.REVISE_PLAN and is_cross_stage_replan_phase(phase):
        count = int(st.get("replan_count") or 0)
        if count >= settings.replan_max_revisions:
            raise AppError(ErrorCode.INVALID_STATE, "跨阶段改策划次数已达上限")
        st = {
            **st,
            "replan_count": count + 1,
            "superseded": {
                "design_doc": st.get("design_doc"),
                "art_direction": st.get("art_direction"),
                "art_options": st.get("art_options"),
                "phase": phase,
                "failure_report_id": st.get("failure_report_id"),
            },
        }

    revision = await bump_control_revision(db, run_id, expected=expected_control_revision)
    payload = {
        **mapped.payload,
        "decision": decision_key,
        "modify_text": modify_text,
        "command": mapped.command_type.value,
    }
    command_row = await insert_run_command(
        db,
        run_id=run_id,
        command_type=mapped.command_type,
        source=mapped.source,
        payload=payload,
        idempotency_key=(f"{run_id}:{revision}:{mapped.command_type.value}:{decision_key}"),
    )
    granted = {
        **st,
        "resume_grant": {
            "decision": decision_key,
            "modify_text": modify_text,
            "command_id": str(command_row.id),
            "command_type": mapped.command_type.value,
        },
    }
    await ckpt.save_state(r, run_id, granted, db)
    await add_task(
        db,
        TASK_RESUME_RUN,
        resume_payload(run_id, decision_key, modify_text, command_id=command_row.id),
    )
    return command_row.id
