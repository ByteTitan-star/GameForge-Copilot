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


def append_hitl_trace(existing: str, *, decision: str, note: str = "") -> str:
    """把本轮 HITL 决策固化下来，避免后续节点清空 modify_text 后完成卡丢意见。"""
    parts = [item for item in (existing or "").split("\n") if item.strip()]
    choice = (decision or "").strip()
    comment = (note or "").strip()
    if choice == "modify" and comment:
        line = comment
    elif choice == "approve":
        line = "已确认策划稿"
    elif choice == "select_a":
        line = "选定美术方案 A"
    elif choice == "select_b":
        line = "选定美术方案 B"
    elif comment:
        line = comment
    else:
        return "\n".join(parts)
    if line not in parts:
        parts.append(line)
    return "\n".join(parts)


def _clip(text: str, limit: int) -> str:
    raw = text.strip()
    if len(raw) <= limit:
        return raw
    return f"{raw[: limit - 1]}…"


def completion_message_content(
    *,
    title: str,
    version: int,
    design_doc: dict | None = None,
    requirement: str = "",
    art_name: str = "",
    user_notes: str = "",
) -> str:
    """完成后的说明：怎么玩结合需求/确认/美术，不把策划稿核心循环再贴一遍。"""
    lines = [
        "# 任务执行已完成",
        "",
        f"**{title or '未命名游戏'}** 已生成，版本 v{version}，可以在右侧试玩。",
        "",
        "## 怎么玩",
    ]
    doc = design_doc if isinstance(design_doc, dict) else {}
    controls = [str(item) for item in (doc.get("controls") or []) if str(item).strip()]
    if controls:
        lines.append(f"- 按你确认过的操作：{'；'.join(controls[:6])}")
    else:
        lines.append("- 按画面内的开始/暂停/重开按钮，以及策划确认过的键位操作")
    req = _clip(requirement, 80)
    if req:
        lines.append(f"- 围绕你的需求「{req}」开局：点开始后按上面的键位玩")
    if str(art_name or "").strip():
        lines.append(f"- 选定「{str(art_name).strip()}」后，用该方向的反馈确认命中、暂停和失败")
    basis: list[str] = []
    if (requirement or "").strip():
        basis.append(f"- 你的需求：{_clip(requirement, 160)}")
    notes = (user_notes or "").strip()
    if notes:
        basis.append(f"- 你的修改意见：{_clip(notes, 160)}")
    if str(art_name or "").strip():
        basis.append(f"- 选定美术：{str(art_name).strip()}")
    if basis:
        lines.extend(["", "## 本次依据", *basis])
        lines.append("- 玩法以你确认过的策划稿和选择为准，不是模型单方面定稿。")
    return "\n".join(lines).strip()


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
