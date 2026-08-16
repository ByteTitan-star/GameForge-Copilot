"""Node-scoped Skill routing：Policy 强制，Methodology 按需选择。"""

from __future__ import annotations

from typing import Any

from app.forge.skills.catalog import list_skill_metas
from app.forge.skills.loader import load_skill_body
from app.forge.skills.models import LoadedSkill, ResolvedSkills, SkillMeta


def resolve_skills_for_node(
    node: str,
    *,
    hints: dict[str, Any] | None = None,
) -> ResolvedSkills:
    """discover(metadata) → choose → load(bodies)。

    Art 节点不会看到 billing/sandbox admin 等未登记 Skill（catalog 白名单即边界）。
    """
    hints = hints or {}
    metas = list_skill_metas()
    node_key = _normalize_node(node)

    policy_metas = [
        m for m in metas if m.kind == "policy" and _node_allowed(m, node_key)
    ]
    candidates = [
        m for m in metas if m.kind == "methodology" and _node_allowed(m, node_key)
    ]
    chosen = _choose_methodology(node_key, candidates, hints)

    policy = tuple(_load(m) for m in policy_metas)
    methodology = tuple(_load(m) for m in chosen)
    return ResolvedSkills(
        policy=policy,
        methodology=methodology,
        loaded_body_count=len(policy) + len(methodology),
    )


def _normalize_node(node: str) -> str:
    n = (node or "").strip().lower()
    aliases = {
        "art_options": "art",
        "revise_art_options": "art",
        "art_detail": "art",
        "code_or_repair": "code",
        "code_qa_loop": "code",
        "revise_plan": "plan",
    }
    return aliases.get(n, n)


def _node_allowed(meta: SkillMeta, node: str) -> bool:
    if not meta.nodes:
        return True
    return node in meta.nodes


def _choose_methodology(
    node: str, candidates: list[SkillMeta], hints: dict[str, Any]
) -> list[SkillMeta]:
    if not candidates:
        return []
    if node in {"art"}:
        return _choose_art(candidates, hints)
    if node in {"code", "repair", "qa", "diagnose"}:
        return _choose_code_or_repair(node, candidates, hints)
    # plan 等：默认不塞 methodology，只保留 policy（若有）
    return []


def _choose_art(candidates: list[SkillMeta], hints: dict[str, Any]) -> list[SkillMeta]:
    text = " ".join(
        str(hints.get(k, "")) for k in ("style", "modify_text", "requirement", "goal")
    ).lower()
    picked: list[SkillMeta] = []
    by_id = {m.id: m for m in candidates}

    if any(k in text for k in ("像素", "pixel")) and "art/pixel-art" in by_id:
        picked.append(by_id["art/pixel-art"])
    if any(k in text for k in ("hud", "血条", "分数", "ui")) and "art/hud-design" in by_id:
        picked.append(by_id["art/hud-design"])
    if "art/visual-composition" in by_id and len(picked) < 2:
        picked.append(by_id["art/visual-composition"])
    if not picked:
        # 默认轻量组合，避免全量注入
        for skill_id in ("art/visual-composition", "art/hud-design"):
            if skill_id in by_id:
                picked.append(by_id[skill_id])
            if len(picked) >= 2:
                break
    return picked[:3]


def _choose_code_or_repair(
    node: str, candidates: list[SkillMeta], hints: dict[str, Any]
) -> list[SkillMeta]:
    engine = str(hints.get("engine_id") or "canvas").strip().lower()
    if engine not in {"canvas", "phaser3", "pixijs"}:
        engine = "canvas"
    by_id = {m.id: m for m in candidates}
    picked: list[SkillMeta] = []
    engine_id = f"code/{engine}"
    if engine_id in by_id:
        picked.append(by_id[engine_id])

    if node in {"repair", "qa", "diagnose"}:
        failure = str(hints.get("failure_kind") or "").lower()
        if failure in {"infra"}:
            if "playtest/observation" in by_id:
                picked.append(by_id["playtest/observation"])
        elif failure in {"product", "build"} or node == "repair":
            if "repair/runtime-error" in by_id:
                picked.append(by_id["repair/runtime-error"])
            if "repair/gameplay-regression" in by_id:
                picked.append(by_id["repair/gameplay-regression"])
            if "playtest/observation" in by_id:
                picked.append(by_id["playtest/observation"])
    return picked


def _load(meta: SkillMeta) -> LoadedSkill:
    return LoadedSkill(
        id=meta.id,
        name=meta.name,
        kind=meta.kind,
        body=load_skill_body(meta.path),
    )
