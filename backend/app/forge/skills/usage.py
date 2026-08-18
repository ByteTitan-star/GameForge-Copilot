"""把本次节点实际加载的 Skill 打进 run 事件日志。"""

from __future__ import annotations

import uuid

from app.enums import WSEventType
from app.forge.events import publish_event
from app.forge.skills.models import ResolvedSkills


async def maybe_publish_skill_usage(
    hints: dict,
    node: str,
    resolved: ResolvedSkills,
) -> None:
    raw = hints.get("run_id")
    if not raw:
        return
    try:
        run_id = uuid.UUID(str(raw))
    except ValueError:
        return
    method_ids = [s.id for s in resolved.methodology]
    if not method_ids:
        return
    method_names = [s.name for s in resolved.methodology]
    policy_ids = [s.id for s in resolved.policy]
    phase = "code" if node in {"repair", "diagnose"} else node
    if phase in {"art_options", "art_detail", "revise_art_options"}:
        phase = "art"
    await publish_event(
        run_id,
        WSEventType.TOOL_CALL,
        {
            "phase": phase,
            "tool": "skill",
            "args": {
                "skill_ids": method_ids,
                "skill_names": method_names,
                "policy_ids": policy_ids,
            },
            "status": "ok",
            "summary": ", ".join(method_names),
        },
    )
