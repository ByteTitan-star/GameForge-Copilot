"""Mocked quality-lift A/B scaffold（无真实 LLM 费用）。"""

from __future__ import annotations

from app.forge.skills.ab_eval import run_mocked_quality_lift_ab


def test_mocked_quality_lift_ab_shows_body_reduction() -> None:
    report = run_mocked_quality_lift_ab()
    assert len(report.cases) >= 4
    assert report.mock_llm_calls == 0
    assert report.avg_reduction >= 0.2
    assert all(c.top_skill for c in report.cases)
