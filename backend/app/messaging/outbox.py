"""Transactional outbox for durable Forge task submission."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import RunStatus
from app.messaging.factory import get_task_publisher
from app.models.generation_run import GenerationRun
from app.models.task_outbox import TaskOutbox

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 10


async def add_task(db: AsyncSession, task: str, payload: dict) -> TaskOutbox:
    row = TaskOutbox(task=task, payload=payload)
    db.add(row)
    await db.flush()
    return row


async def cancel_run_tasks(db: AsyncSession, run_id: uuid.UUID) -> int:
    """Mark unpublished tasks for a cancelled run as handled."""
    rows = list(
        (
            await db.scalars(
                select(TaskOutbox).where(TaskOutbox.published_at.is_(None))
            )
        ).all()
    )
    now = datetime.now(UTC)
    matched = 0
    for row in rows:
        if str(row.payload.get("run_id")) == str(run_id):
            row.published_at = now
            row.last_error = "cancelled before dispatch"
            matched += 1
    return matched


async def dispatch_pending(limit: int = 50) -> int:
    """Publish due rows. A crash after publish may duplicate a task, never lose it."""
    from app.core import db as dbmod

    published = 0
    async with dbmod.SessionLocal() as db:
        stmt = (
            select(TaskOutbox)
            .where(
                TaskOutbox.published_at.is_(None),
                TaskOutbox.next_attempt_at <= datetime.now(UTC),
            )
            .order_by(TaskOutbox.created_at)
            .limit(limit)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        rows = list((await db.scalars(stmt)).all())
        publisher = get_task_publisher()
        for row in rows:
            try:
                await publisher.publish(row.task, dict(row.payload))
            except Exception as exc:
                row.attempts += 1
                row.last_error = str(exc)[:4000]
                if row.attempts >= MAX_ATTEMPTS:
                    row.published_at = datetime.now(UTC)
                    run_id = row.payload.get("run_id")
                    if run_id:
                        run = await db.get(GenerationRun, uuid.UUID(str(run_id)))
                        if run is not None and run.ended_at is None:
                            run.status = RunStatus.FAILED.value
                            run.ended_at = datetime.now(UTC)
                    log.error("outbox task exhausted retries id=%s task=%s", row.id, row.task)
                else:
                    delay = min(2 ** row.attempts, 300)
                    row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
                    log.warning("outbox publish failed id=%s retry_in=%ss", row.id, delay)
            else:
                row.published_at = datetime.now(UTC)
                row.last_error = None
                published += 1
        await db.commit()
    return published
