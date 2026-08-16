"""P2 质量 lift A/B：默认 mock；可选 LLM complete（flag 默认关）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.forge.skills.catalog import list_skill_metas
from app.forge.skills.loader import load_skill_body
from app.forge.skills.router import resolve_skills_for_node, resolve_skills_for_node_async

LlmComplete = Callable[[str, str], Awaitable[str]]


@dataclass(frozen=True)
class AbCaseResult:
    node: str
    routed_chars: int
    full_chars: int
    reduction: float
    top_skill: str
    llm_used: bool = False


@dataclass(frozen=True)
class AbReport:
    cases: tuple[AbCaseResult, ...]
    avg_reduction: float
    mock_llm_calls: int
    llm_calls: int = 0


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
        results.append(_case_from_routed(node, routed))
    return _report(results, llm_calls=0)


async def run_quality_lift_ab(
    *,
    complete: LlmComplete | None = None,
    cases: tuple[tuple[str, dict[str, Any]], ...] | None = None,
) -> AbReport:
    """Flag 开且提供 complete 时走 LLM 路由；否则等价 mock。

    真实付费调用仍须运维显式打开 `skills_quality_lift_llm` 并注入 complete。
    """
    use_llm = bool(settings.skills_quality_lift_llm and complete is not None)
    results: list[AbCaseResult] = []
    llm_calls = 0
    for node, hints in cases or _DEFAULT_CASES:
        if use_llm:
            routed = await resolve_skills_for_node_async(
                node, hints=hints, complete=complete
            )
            llm_calls += 1
            results.append(_case_from_routed(node, routed, llm_used=True))
        else:
            routed = resolve_skills_for_node(node, hints=hints)
            results.append(_case_from_routed(node, routed, llm_used=False))
    return _report(results, llm_calls=llm_calls)


def _case_from_routed(node: str, routed: Any, *, llm_used: bool = False) -> AbCaseResult:
    routed_chars = sum(len(s.body) for s in routed.methodology)
    full_meth = [
        m
        for m in list_skill_metas()
        if m.kind == "methodology" and (not m.nodes or node in m.nodes)
    ]
    full_chars = sum(len(load_skill_body(m.path)) for m in full_meth)
    reduction = (1.0 - routed_chars / full_chars) if full_chars else 0.0
    top = routed.methodology[0].id if routed.methodology else ""
    return AbCaseResult(
        node=node,
        routed_chars=routed_chars,
        full_chars=full_chars,
        reduction=reduction,
        top_skill=top,
        llm_used=llm_used,
    )


def _report(results: list[AbCaseResult], *, llm_calls: int) -> AbReport:
    avg = sum(r.reduction for r in results) / len(results) if results else 0.0
    return AbReport(
        cases=tuple(results),
        avg_reduction=avg,
        mock_llm_calls=0 if llm_calls else 0,
        llm_calls=llm_calls,
    )
