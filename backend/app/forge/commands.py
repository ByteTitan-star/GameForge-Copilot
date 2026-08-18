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
    from app.core import db as dbmod

    async with dbmod.SessionLocal() as db:
        row = await db.get(RunCommand, command_id)
        return row is not None and row.status == RunCommandStatus.SUCCEEDED.value


async def _set_command_succeeded(db: AsyncSession, command_id: uuid.UUID) -> None:
    await db.execute(
        update(RunCommand)
        .where(RunCommand.id == command_id)
        .values(
            status=RunCommandStatus.SUCCEEDED.value,
            completed_at=datetime.now(UTC),
        )
    )


async def mark_command_succeeded(command_id: uuid.UUID, db: AsyncSession | None = None) -> None:
    if db is not None:
        await _set_command_succeeded(db, command_id)
        return
    from app.core import db as dbmod

    async with dbmod.SessionLocal() as session:
        await _set_command_succeeded(session, command_id)
        await session.commit()
