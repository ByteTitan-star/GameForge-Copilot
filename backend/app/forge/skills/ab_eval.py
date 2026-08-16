"""P2 质量 lift A/B scaffold：mock，不打真实 API。

真实付费 A/B 仍 gated；用 Methodology body 长度对比路由 vs 全量注入。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.forge.skills.catalog import list_skill_metas
from app.forge.skills.loader import load_skill_body
from app.forge.skills.router import resolve_skills_for_node


@dataclass(frozen=True)
class AbCaseResult:
    node: str
    routed_chars: int
    full_chars: int
    reduction: float
    top_skill: str


@dataclass(frozen=True)
class AbReport:
    cases: tuple[AbCaseResult, ...]
    avg_reduction: float
    mock_llm_calls: int


_DEFAULT_CASES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("art", {"style": "像素风"}),
    ("art", {"style": "HUD 血条"}),
    ("code", {"engine_id": "phaser3"}),
    ("repair", {"engine_id": "canvas", "failure_kind": "product"}),
)


def run_mocked_quality_lift_ab(
    cases: tuple[tuple[str, dict[str, Any]], ...] | None = None,
) -> AbReport:
    """本地 body 长度近似 token；不发起 LLM。"""
    results: list[AbCaseResult] = []
    for node, hints in cases or _DEFAULT_CASES:
        routed = resolve_skills_for_node(node, hints=hints)
        routed_chars = sum(len(s.body) for s in routed.methodology)
        full_meth = [
            m
            for m in list_skill_metas()
            if m.kind == "methodology" and (not m.nodes or node in m.nodes)
        ]
        full_chars = sum(len(load_skill_body(m.path)) for m in full_meth)
        reduction = (1.0 - routed_chars / full_chars) if full_chars else 0.0
        top = routed.methodology[0].id if routed.methodology else ""
        results.append(
            AbCaseResult(
                node=node,
                routed_chars=routed_chars,
                full_chars=full_chars,
                reduction=reduction,
                top_skill=top,
            )
        )
    avg = sum(r.reduction for r in results) / len(results) if results else 0.0
    return AbReport(cases=tuple(results), avg_reduction=avg, mock_llm_calls=0)
