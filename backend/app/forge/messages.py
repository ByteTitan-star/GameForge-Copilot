from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.forge.design_doc import design_doc_to_readable_text
from app.models.forge_message import ForgeMessage


async def add_message(
    db: AsyncSession,
    *,
    game_id: uuid.UUID,
    run_id: uuid.UUID | None,
    user_id: uuid.UUID,
    role: str,
    kind: str,
    content: str,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
) -> ForgeMessage:
    if dedupe_key:
        existing = await db.scalar(
            select(ForgeMessage).where(ForgeMessage.dedupe_key == dedupe_key)
        )
        if existing is not None:
            return existing
    row = ForgeMessage(
        game_id=game_id,
        run_id=run_id,
        user_id=user_id,
        role=role,
        kind=kind,
        content=content,
        metadata_json=metadata or {},
        dedupe_key=dedupe_key,
        created_at=datetime.now(UTC),
    )
    if not dedupe_key:
        db.add(row)
        return row
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
        return row
    except IntegrityError:
        existing = await db.scalar(
            select(ForgeMessage).where(ForgeMessage.dedupe_key == dedupe_key)
        )
        if existing is None:
            raise
        return existing


def design_message_content(design_doc: dict | str) -> str:
    if not isinstance(design_doc, dict):
        return f"设计方案已生成：{design_doc}"
    body = design_doc_to_readable_text(design_doc)
    return f"{body}\n\n请确认方案，或填写修改意见。"


def stable_design_key(run_id: uuid.UUID, node: str, design_doc: dict | str) -> str:
    raw = json.dumps(design_doc, ensure_ascii=False, sort_keys=True, default=str)
    return f"{run_id}:design:{node}:{uuid.uuid5(uuid.NAMESPACE_OID, raw)}"


def stable_payload_key(run_id: uuid.UUID, kind: str, payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return f"{run_id}:{kind}:{uuid.uuid5(uuid.NAMESPACE_OID, raw)}"


async def list_messages(
    db: AsyncSession,
    game_id: uuid.UUID,
    *,
    limit: int,
    before: uuid.UUID | None,
) -> list[ForgeMessage]:
    query = select(ForgeMessage).where(ForgeMessage.game_id == game_id)
    if before is not None:
        cursor = await db.scalar(
            select(ForgeMessage).where(ForgeMessage.id == before, ForgeMessage.game_id == game_id)
        )
        if cursor is None:
            return []
        query = query.where(
            or_(
                ForgeMessage.created_at < cursor.created_at,
                and_(
                    ForgeMessage.created_at == cursor.created_at,
                    ForgeMessage.id < cursor.id,
                ),
            )
        )
    rows = (
        await db.scalars(
            query.order_by(ForgeMessage.created_at.desc(), ForgeMessage.id.desc()).limit(limit)
        )
    ).all()
    return list(reversed(rows))
