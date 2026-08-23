"""Node-scoped Skill routing：Policy 强制，Methodology 按需选择。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import settings
from app.forge.skills.catalog import list_skill_metas
from app.forge.skills.loader import load_skill_body
from app.forge.skills.models import LoadedSkill, ResolvedSkills, SkillMeta

LlmComplete = Callable[[str, str], Awaitable[str]]


def resolve_skills_for_node(
    node: str,
    *,
    hints: dict[str, Any] | None = None,
) -> ResolvedSkills:
    """discover(metadata) → choose → load(bodies)。

    Art 节点不会看到 billing/sandbox admin 等未登记 Skill（catalog 白名单即边界）。
    hints.methodology_ids 若提供：仅在候选白名单内覆盖 Methodology 选择（Policy 仍强制）。
    """
    from app.forge.tracing import observe_subsystem

    hints = hints or {}
    with observe_subsystem("skill", "resolve", metadata={"node": node}):
        return _resolve(node, hints)


async def resolve_skills_for_node_async(
    node: str,
    *,
    hints: dict[str, Any] | None = None,
    complete: LlmComplete | None = None,
) -> ResolvedSkills:
    """可选 LLM 自选 Methodology；失败或关 flag 时回落确定性路由。Policy 始终强制。"""
    from app.forge.tracing import observe_subsystem

    hints = dict(hints or {})
    with observe_subsystem(
        "skill",
        "resolve_async",
        metadata={"node": node, "llm": bool(settings.skills_llm_selection and complete)},
    ):
        if (
            settings.skills_llm_selection
            and complete is not None
            and "methodology_ids" not in hints
        ):
            node_key = _normalize_node(node)
            candidates = [
                m
                for m in list_skill_metas()
                if m.kind == "methodology" and _node_allowed(m, node_key)
            ]
            from app.forge.skills.llm_select import select_methodology_ids_via_llm

            selected = await select_methodology_ids_via_llm(
                node=node_key,
                candidates=candidates,
                hints=hints,
                complete=complete,
            )
            if selected is not None:
                hints["methodology_ids"] = selected
        return _resolve(node, hints)


def _resolve(node: str, hints: dict[str, Any]) -> ResolvedSkills:
    """按节点解析 Policy + Methodology Skill 并加载正文。

    场景：resolve_skills_for_node 内部。
    参数：node、hints（可含 methodology_ids 覆盖）。
    返回：ResolvedSkills。
    """
    metas = list_skill_metas()
    node_key = _normalize_node(node)

    policy_metas = [m for m in metas if m.kind == "policy" and _node_allowed(m, node_key)]
    candidates = [m for m in metas if m.kind == "methodology" and _node_allowed(m, node_key)]
    chosen = _choose_methodology(node_key, candidates, hints)

    policy = tuple(_load(m) for m in policy_metas)
    methodology = tuple(_load(m) for m in chosen)
    return ResolvedSkills(
        policy=policy,
        methodology=methodology,
        loaded_body_count=len(policy) + len(methodology),
    )


def _normalize_node(node: str) -> str:
    """将 graph 节点名映射到 skill catalog 的 node 键。

    场景：resolve / _node_allowed。
    参数：node - 如 art_options、code_or_repair。
    返回：art、code、plan 等规范名。
    """
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
    """判断 Skill 元数据是否允许挂载到该节点。

    场景：筛选 policy/methodology 候选。
    参数：meta、node - 规范节点名。
    返回：meta.nodes 为空或含 node 时为 True。
    """
    if not meta.nodes:
        return True
    return node in meta.nodes


def _choose_methodology(
    node: str, candidates: list[SkillMeta], hints: dict[str, Any]
) -> list[SkillMeta]:
    """按节点与 hints 从候选 Methodology 中选出最多 3 个。

    场景：_resolve 组装 methodology 列表。
    参数：node、candidates、hints。
    返回：选中的 SkillMeta 列表。
    """
    if not candidates:
        return []
    override = hints.get("methodology_ids")
    if isinstance(override, (list, tuple)) and override:
        by_id = {m.id: m for m in candidates}
        picked = [by_id[i] for i in override if isinstance(i, str) and i in by_id]
        if picked:
            return picked[:3]
    if node in {"art"}:
        return _choose_art(candidates, hints)
    if node in {"code", "repair", "qa", "diagnose"}:
        return _choose_code_or_repair(node, candidates, hints)
    return []


_ART_STYLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("art/pixel-art", ("像素", "pixel")),
    ("art/paper-craft", ("纸", "剪纸", "折纸", "paper", "origami", "拼贴")),
    ("art/ink-wash", ("水墨", "国风", "山水", "ink", "毛笔")),
    ("art/candy-arcade", ("糖果", "卡通", "可爱", "candy", "cartoon", "休闲")),
    ("art/crt-analog", ("crt", "磁带", "复古电视", "vhs", "扫描线", "磷光")),
)


def _choose_art(candidates: list[SkillMeta], hints: dict[str, Any]) -> list[SkillMeta]:
    """按风格关键词为 art 节点选择 Methodology Skill。

    场景：_choose_methodology node==art。
    参数：candidates、hints（style/requirement 等）。
    返回：最多 3 个 SkillMeta。
    """
    text = " ".join(
        str(hints.get(k, "")) for k in ("style", "modify_text", "requirement", "goal")
    ).lower()
    picked: list[SkillMeta] = []
    by_id = {m.id: m for m in candidates}

    for skill_id, keys in _ART_STYLE_KEYWORDS:
        if skill_id in by_id and any(k in text for k in keys):
            picked.append(by_id[skill_id])
        if len(picked) >= 2:
            break
    if (
        any(k in text for k in ("hud", "血条", "分数", "ui"))
        and "art/hud-design" in by_id
        and by_id["art/hud-design"] not in picked
    ):
        picked.append(by_id["art/hud-design"])
    if "art/visual-composition" in by_id and len(picked) < 2:
        picked.append(by_id["art/visual-composition"])
    if not picked:
        for skill_id in ("art/visual-composition", "art/hud-design"):
            if skill_id in by_id:
                picked.append(by_id[skill_id])
            if len(picked) >= 2:
                break
    return picked[:3]


def _choose_code_or_repair(
    node: str, candidates: list[SkillMeta], hints: dict[str, Any]
) -> list[SkillMeta]:
    """按引擎与失败类型为 code/repair/qa 节点选择 Skill。

    场景：_choose_methodology code 分支。
    参数：node、candidates、hints（engine_id、failure_kind）。
    返回：匹配的 SkillMeta 列表。
    """
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
    """从磁盘加载 Skill 正文并包装为 LoadedSkill。

    场景：_resolve 最终组装。
    参数：meta - Skill 元数据。
    返回：含 body 的 LoadedSkill。
    """
    return LoadedSkill(
        id=meta.id,
        name=meta.name,
        kind=meta.kind,
        body=load_skill_body(meta.path),
    )
