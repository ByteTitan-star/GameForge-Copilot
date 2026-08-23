"""Resume Command 规范化与幂等：所有入队路径共享同一边界。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.enums import PauseReason, RunCommandStatus, RunCommandType
from app.models.generation_run import GenerationRun
from app.models.run_command import RunCommand

CURRENT_WORKFLOW_VERSION = 1

_LEGACY_DECISION_MAP: dict[tuple[str, str], RunCommandType] = {
    ("plan_confirm", "approve"): RunCommandType.APPROVE_PLAN,
    ("plan_confirm", "modify"): RunCommandType.REVISE_PLAN,
    ("art_confirm", "select_a"): RunCommandType.SELECT_ART_A,
    ("art_confirm", "select_b"): RunCommandType.SELECT_ART_B,
    ("art_confirm", "modify"): RunCommandType.REVISE_ART,
    ("qa_failed", "approve"): RunCommandType.RETRY_IMPLEMENTATION,
    ("qa_failed", "modify"): RunCommandType.RETRY_IMPLEMENTATION,
    ("sandbox_failed", "approve"): RunCommandType.RETRY_IMPLEMENTATION,
    ("sandbox_failed", "modify"): RunCommandType.RETRY_IMPLEMENTATION,
}

_COMMAND_TO_LEGACY_DECISION: dict[RunCommandType, str] = {
    RunCommandType.APPROVE_PLAN: "approve",
    RunCommandType.REVISE_PLAN: "modify",
    RunCommandType.SELECT_ART_A: "select_a",
    RunCommandType.SELECT_ART_B: "select_b",
    RunCommandType.REVISE_ART: "modify",
    RunCommandType.RETRY_IMPLEMENTATION: "approve",
    RunCommandType.RETRY_INFRA: "approve",
    RunCommandType.CANCEL_RUN: "cancel",
}


@dataclass(frozen=True)
class NormalizedCommand:
    command_type: RunCommandType
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


def legacy_decision_for(command_type: RunCommandType) -> str:
    """将 RunCommandType 映射为 legacy decision 字符串。

    场景：``enqueue_resume`` 写入 resume_grant 与 RabbitMQ payload。
    参数：command_type - RunCommandType 枚举值。
    返回：如 approve/modify/select_a 等 legacy 决策键。
    """
    return _COMMAND_TO_LEGACY_DECISION.get(command_type, "approve")


def normalize_resume_command(
    *,
    phase: str | None,
    decision: str,
    pause_reason: str | None = None,
    source: str = "hitl",
    feedback: str | None = None,
    command: str | None = None,
) -> NormalizedCommand:
    """将 phase + decision/command 规范化为 RunCommandType 与 payload。

    场景：``enqueue_resume`` 统一 resume 入队边界（ADR-10）。
    参数：
        phase - 当前 HITL phase；
        decision - legacy 决策键；
        pause_reason - 可选暂停原因；
        source - 命令来源；
        feedback - 可选用户反馈文本；
        command - 可选显式 RunCommandType 值。
    返回：NormalizedCommand（command_type、source、payload）。
    """
    phase_key = (phase or "").strip()
    decision_key = (decision or "").strip()
    command_key = (command or "").strip()
    payload: dict[str, Any] = {}
    note = (feedback or "").strip()
    if note:
        payload["feedback"] = note

    if command_key:
        try:
            command_type = RunCommandType(command_key)
        except ValueError as exc:
            raise AppError(ErrorCode.INVALID_STATE, f"未知命令: {command_key}") from exc
        return NormalizedCommand(command_type, source, payload)

    mapped = _LEGACY_DECISION_MAP.get((phase_key, decision_key))
    if mapped is not None:
        return NormalizedCommand(mapped, source, payload)
    if pause_reason == PauseReason.RECOVERABLE_ERROR.value:
        return NormalizedCommand(RunCommandType.RETRY_INFRA, source, payload)
    return NormalizedCommand(RunCommandType.RETRY_IMPLEMENTATION, source, payload)


async def bump_control_revision(
    db: AsyncSession, run_id: uuid.UUID, *, expected: int | None = None
) -> int:
    """乐观锁递增 GenerationRun.control_revision。

    场景：每次 resume/cancel 前 CAS 防并发决策冲突。
    参数：db - 异步数据库会话；run_id - 生成任务 ID；expected - 可选期望当前版本。
    返回：递增后的 control_revision；版本不匹配时抛 STALE_DECISION。
    """
    stmt = update(GenerationRun).where(GenerationRun.id == run_id)
    if expected is not None:
        stmt = stmt.where(GenerationRun.control_revision == expected)
    result = await db.execute(stmt.values(control_revision=GenerationRun.control_revision + 1))
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise AppError(ErrorCode.STALE_DECISION, "决策已过期，请刷新后重试")
    await db.flush()
    run = await db.get(GenerationRun, run_id)
    if run is None:
        raise AppError(ErrorCode.STALE_DECISION, "决策已过期，请刷新后重试")
    await db.refresh(run)
    return int(run.control_revision)


async def insert_run_command(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    command_type: RunCommandType,
    source: str,
    payload: dict[str, Any],
    idempotency_key: str,
    status: RunCommandStatus = RunCommandStatus.PENDING,
) -> RunCommand:
    """插入一条 RunCommand 记录。

    场景：``enqueue_resume`` / ``record_cancel_command`` 写入命令审计。
    参数：
        db - 异步数据库会话；
        run_id - 生成任务 ID；
        command_type - 命令类型；
        source - 来源标识；
        payload - 命令载荷 dict；
        idempotency_key - 幂等键；
        status - 初始状态（默认 PENDING）。
    返回：新建的 RunCommand ORM 行。
    """
    row = RunCommand(
        run_id=run_id,
        command_type=command_type.value,
        source=source,
        payload=payload,
        idempotency_key=idempotency_key,
        status=status.value,
    )
    db.add(row)
    await db.flush()
    return row


async def record_cancel_command(db: AsyncSession, run_id: uuid.UUID) -> RunCommand:
    """记录取消命令并直接标记为 SUCCEEDED。

    场景：用户取消 run 时写入审计记录。
    参数：db - 异步数据库会话；run_id - 生成任务 ID。
    返回：已完成的 CANCEL_RUN RunCommand 行。
    """
    revision = await bump_control_revision(db, run_id)
    now = datetime.now(UTC)
    row = await insert_run_command(
        db,
        run_id=run_id,
        command_type=RunCommandType.CANCEL_RUN,
        source="cancel",
        payload={},
        idempotency_key=f"{run_id}:{revision}:{RunCommandType.CANCEL_RUN.value}",
        status=RunCommandStatus.SUCCEEDED,
    )
    row.completed_at = now
    return row


async def command_already_succeeded(command_id: uuid.UUID) -> bool:
    """检查 RunCommand 是否已成功执行（幂等跳过）。

    场景：``resume_run`` worker 入口防 at-least-once 重复执行。
    参数：command_id - RunCommand ID。
    返回：status 为 SUCCEEDED 时为 True。
    """
    from app.core import db as dbmod

    async with dbmod.SessionLocal() as db:
        row = await db.get(RunCommand, command_id)
        return row is not None and row.status == RunCommandStatus.SUCCEEDED.value


async def _set_command_succeeded(db: AsyncSession, command_id: uuid.UUID) -> None:
    """将 RunCommand 状态更新为 SUCCEEDED 并记录完成时间。

    场景：``mark_command_succeeded`` 内部实现。
    参数：db - 异步数据库会话；command_id - RunCommand ID。
    返回：无。
    """
    await db.execute(
        update(RunCommand)
        .where(RunCommand.id == command_id)
        .values(
            status=RunCommandStatus.SUCCEEDED.value,
            completed_at=datetime.now(UTC),
        )
    )


async def mark_command_succeeded(command_id: uuid.UUID, db: AsyncSession | None = None) -> None:
    """标记 RunCommand 为已成功执行。

    场景：``resume_run`` worker 完成 resume 流程后更新命令状态。
    参数：command_id - RunCommand ID；db - 可选 DB 会话（无则自建会话并 commit）。
    返回：无。
    """
    if db is not None:
        await _set_command_succeeded(db, command_id)
        return
    from app.core import db as dbmod

    async with dbmod.SessionLocal() as session:
        await _set_command_succeeded(session, command_id)
        await session.commit()
