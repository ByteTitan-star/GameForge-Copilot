"""P2 离线 eval：selection precision 与相对全量 Methodology 注入的 quality lift。

无 lift / precision 不达标则不应继续扩 catalog（见 runtime evolution 计划 P2 Go/No-Go）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.forge.skills.catalog import list_skill_metas
from app.forge.skills.router import resolve_skills_for_node

MatchMode = Literal["top", "member"]

# (node, hints, expected_id, match_mode)
EVAL_FIXTURES: tuple[tuple[str, dict[str, Any], str, MatchMode], ...] = (
    ("art", {"style": "像素风"}, "art/pixel-art", "top"),
    ("art", {"style": "pixel art"}, "art/pixel-art", "top"),
    ("art", {"style": "HUD 血条分数"}, "art/hud-design", "top"),
    ("art", {"style": "清晰 UI"}, "art/hud-design", "top"),
    ("art", {"style": "构图对比"}, "art/visual-composition", "top"),
    ("art", {"requirement": "默认视觉"}, "art/visual-composition", "top"),
    ("code", {"engine_id": "canvas"}, "code/canvas", "top"),
    ("code", {"engine_id": "phaser3"}, "code/phaser3", "top"),
    ("code", {"engine_id": "pixijs"}, "code/pixijs", "top"),
    ("repair", {"engine_id": "canvas", "failure_kind": "product"}, "code/canvas", "top"),
    (
        "repair",
        {"engine_id": "canvas", "failure_kind": "product"},
        "repair/runtime-error",
        "member",
    ),
    (
        "repair",
        {"engine_id": "phaser3", "failure_kind": "build"},
        "repair/gameplay-regression",
        "member",
    ),
    (
        "diagnose",
        {"engine_id": "canvas", "failure_kind": "infra"},
        "playtest/observation",
        "member",
    ),
    (
        "art_detail",
        {"style": "像素风"},
        "art/pixel-art",
        "member",
    ),
    (
        "qa",
        {"engine_id": "pixijs", "failure_kind": "product"},
        "repair/runtime-error",
        "member",
    ),
    ("art", {"methodology_ids": ["art/pixel-art"]}, "art/pixel-art", "top"),
)


@dataclass(frozen=True)
class EvalReport:
    case_count: int
    precision_at_1: float
    expected_hit_rate: float
    avg_body_reduction: float
    policy_coverage: float
    cross_scope_violations: int
    avg_routed_methodology: float
    avg_full_methodology: float
    top_case_count: int
    member_case_count: int


def evaluate_routing(
    fixtures: (
        tuple[tuple[str, dict[str, Any], str, MatchMode], ...]
        | list[tuple[str, dict[str, Any], str, MatchMode]]
        | None
    ) = None,
) -> EvalReport:
    """对固定 fixtures 跑确定性路由，产出 precision 与 body 压缩指标。"""
    cases = list(fixtures or EVAL_FIXTURES)
    if not cases:
        return EvalReport(0, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, 0, 0)

    top_hits = 0
    top_n = 0
    member_hits = 0
    member_n = 0
    policy_ok = 0
    reductions: list[float] = []
    routed_counts: list[int] = []
    full_counts: list[int] = []
    violations = 0

    for node, hints, expected, mode in cases:
        resolved = resolve_skills_for_node(node, hints=hints)
        meth_ids = [s.id for s in resolved.methodology]
        top = meth_ids[0] if meth_ids else ""
        if mode == "top":
            top_n += 1
            if top == expected:
                top_hits += 1
        else:
            member_n += 1
            if expected in meth_ids:
                member_hits += 1

        expected_policy = _has_policy_for_node(node)
        if not expected_policy or resolved.policy:
            policy_ok += 1

        full_n = _full_methodology_count(node)
        routed_n = len(resolved.methodology)
        full_counts.append(full_n)
        routed_counts.append(routed_n)
        if full_n > 0:
            reductions.append(1.0 - (routed_n / full_n))

        if _normalize_art(node):
            for sid in [*meth_ids, *[s.id for s in resolved.policy]]:
                if sid.startswith(("code/", "repair/", "billing/", "sandbox/")):
                    violations += 1

    n = len(cases)
    return EvalReport(
        case_count=n,
        precision_at_1=(top_hits / top_n) if top_n else 0.0,
        expected_hit_rate=(member_hits / member_n) if member_n else 1.0,
        avg_body_reduction=(sum(reductions) / len(reductions)) if reductions else 0.0,
        policy_coverage=policy_ok / n,
        cross_scope_violations=violations,
        avg_routed_methodology=(sum(routed_counts) / n) if n else 0.0,
        avg_full_methodology=(sum(full_counts) / n) if n else 0.0,
        top_case_count=top_n,
        member_case_count=member_n,
    )


def routing_beats_full_injection(report: EvalReport, *, min_reduction: float = 0.25) -> bool:
    """Go 条件：有显著 body 压缩且 precision 可用。"""
    return (
        report.case_count >= 12
        and report.precision_at_1 >= 0.95
        and report.expected_hit_rate >= 0.95
        and report.avg_body_reduction >= min_reduction
        and report.cross_scope_violations == 0
    )


def _normalize_art(node: str) -> bool:
    """判断节点是否属于 art 子图范围。

    场景：offline_eval 跨域违规检测。
    参数：node - 原始节点名。
    返回：art 相关节点时为 True。
    """
    return (node or "").strip().lower() in {
        "art",
        "art_options",
        "revise_art_options",
        "art_detail",
    }


def _has_policy_for_node(node: str) -> bool:
    """判断 catalog 中是否存在应挂载到该节点的 Policy Skill。

    场景：offline_eval policy_coverage 统计。
    参数：node。
    返回：存在匹配 policy 时为 True。
    """
    from app.forge.skills.router import _node_allowed, _normalize_node

    node_key = _normalize_node(node)
    return any(m.kind == "policy" and _node_allowed(m, node_key) for m in list_skill_metas())


def _full_methodology_count(node: str) -> int:
    """统计某节点允许的全量 Methodology Skill 数量。

    场景：offline_eval body 压缩率计算。
    参数：node。
    返回：候选 methodology 个数。
    """
    from app.forge.skills.router import _node_allowed, _normalize_node

    node_key = _normalize_node(node)
    return sum(
        1 for m in list_skill_metas() if m.kind == "methodology" and _node_allowed(m, node_key)
    )
