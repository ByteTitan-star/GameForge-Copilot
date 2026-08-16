"""P2 离线 eval：Skill routing precision 与相对全量注入的 quality lift。"""

from __future__ import annotations

from app.forge.skills.offline_eval import (
    EVAL_FIXTURES,
    evaluate_routing,
    routing_beats_full_injection,
)


def test_offline_eval_precision_at_least_095() -> None:
    report = evaluate_routing(EVAL_FIXTURES)
    assert report.case_count >= 12
    assert report.precision_at_1 >= 0.95
    assert report.expected_hit_rate >= 0.95


def test_offline_eval_quality_lift_vs_full_injection() -> None:
    report = evaluate_routing(EVAL_FIXTURES)
    assert report.avg_body_reduction >= 0.25
    assert routing_beats_full_injection(report)


def test_offline_eval_policy_always_present_never_cross_scope() -> None:
    report = evaluate_routing(EVAL_FIXTURES)
    assert report.policy_coverage == 1.0
    assert report.cross_scope_violations == 0
