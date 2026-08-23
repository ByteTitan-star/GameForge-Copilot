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
    """写入一条 ForgeMessage，支持 dedupe_key 幂等。

    场景：graph 节点产出设计稿/完成卡/HITL 消息；用户消息落库。
    参数：
        db - 异步数据库会话；
        game_id - 游戏 ID；
        run_id - 关联生成任务 ID（可选）；
        user_id - 用户 ID；
        role - 消息角色（user/assistant 等）；
        kind - 消息类型；
        content - 消息正文；
        metadata - 可选元数据 dict；
        dedupe_key - 可选幂等键。
    返回：新建或已存在的 ForgeMessage 行。
    """
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
    """将设计稿格式化为面向用户的确认消息正文。

    场景：plan 节点 HITL 中断时写入 assistant 消息。
    参数：design_doc - 设计稿 dict 或原始字符串。
    返回：可读文本 + 「请确认方案，或填写修改意见。」
    """
    if not isinstance(design_doc, dict):
        return f"设计方案已生成：{design_doc}"
    body = design_doc_to_readable_text(design_doc)
    return f"{body}\n\n请确认方案，或填写修改意见。"


def append_hitl_trace(existing: str, *, decision: str, note: str = "") -> str:
    """把本轮 HITL 决策固化到用户意见轨迹，避免后续节点清空后丢失。

    场景：resume 流程中累积用户确认/修改/美术选择记录。
    参数：existing - 已有轨迹文本；decision - 决策键；note - 可选附注。
    返回：去重追加后的多行文本。
    """
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
    """按字符数截断文本，超出时加省略号。

    场景：``completion_message_content`` 控制需求/意见展示长度。
    参数：text - 原文；limit - 最大字符数。
    返回：截断后的字符串。
    """
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
    """生成任务完成后的说明消息（怎么玩 + 本次依据）。

    场景：done 节点写入 assistant 完成卡。
    参数：
        title - 游戏标题；
        version - 版本号；
        design_doc - 可选设计稿 dict；
        requirement - 用户需求摘要；
        art_name - 选定美术方案名；
        user_notes - 用户修改意见轨迹。
    返回：Markdown 格式的完成说明正文。
    """
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
    """为设计稿消息生成稳定的 dedupe_key。

    场景：``add_message`` 防止同一 run+node 重复写入设计稿消息。
    参数：run_id - 生成任务 ID；node - 节点名；design_doc - 设计稿内容。
    返回：``{run_id}:design:{node}:{uuid5}`` 格式字符串。
    """
    raw = json.dumps(design_doc, ensure_ascii=False, sort_keys=True, default=str)
    return f"{run_id}:design:{node}:{uuid.uuid5(uuid.NAMESPACE_OID, raw)}"


def stable_payload_key(run_id: uuid.UUID, kind: str, payload: object) -> str:
    """为任意 payload 消息生成稳定的 dedupe_key。

    场景：完成卡、系统通知等需幂等写入的消息。
    参数：run_id - 生成任务 ID；kind - 消息种类；payload - 可 JSON 序列化的内容。
    返回：``{run_id}:{kind}:{uuid5}`` 格式字符串。
    """
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return f"{run_id}:{kind}:{uuid.uuid5(uuid.NAMESPACE_OID, raw)}"


async def list_messages(
    db: AsyncSession,
    game_id: uuid.UUID,
    *,
    limit: int,
    before: uuid.UUID | None,
) -> list[ForgeMessage]:
    """分页查询游戏消息历史（游标 before，时间正序返回）。

    场景：前端聊天面板加载历史消息。
    参数：
        db - 异步数据库会话；
        game_id - 游戏 ID；
        limit - 每页条数；
        before - 可选游标消息 ID（取更早的消息）。
    返回：按时间正序的 ForgeMessage 列表。
    """
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
