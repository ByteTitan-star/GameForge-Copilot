"""Mocked / optional-LLM quality-lift A/B。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.skills.ab_eval import run_mocked_quality_lift_ab, run_quality_lift_ab


def test_mocked_quality_lift_ab_shows_body_reduction() -> None:
    report = run_mocked_quality_lift_ab()
    assert len(report.cases) >= 4
    assert report.mock_llm_calls == 0
    assert report.llm_calls == 0
    assert report.avg_reduction >= 0.2
    assert all(c.top_skill for c in report.cases)


@pytest.mark.asyncio
async def test_quality_lift_ab_llm_path_flag_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "skills_quality_lift_llm", False)

    async def complete(_s: str, _u: str) -> str:
        return '{"skill_ids":["art/pixel-art"]}'

    report = await run_quality_lift_ab(complete=complete)
    assert report.llm_calls == 0

    monkeypatch.setattr(settings, "skills_quality_lift_llm", True)
    report2 = await run_quality_lift_ab(complete=complete)
    assert report2.llm_calls >= 1
    assert any(c.llm_used for c in report2.cases)
