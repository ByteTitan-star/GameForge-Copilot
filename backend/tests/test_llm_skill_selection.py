"""P2：LLM Skill 自选与离线 selection precision 轻量 eval。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.skills.llm_select import select_methodology_ids_via_llm
from app.forge.skills.router import resolve_skills_for_node, resolve_skills_for_node_async


def test_methodology_ids_hint_overrides_deterministic() -> None:
    resolved = resolve_skills_for_node(
        "art",
        hints={"methodology_ids": ["art/pixel-art"], "style": "hud"},
    )
    ids = [s.id for s in resolved.methodology]
    assert ids == ["art/pixel-art"]
    assert any(s.id.startswith("policy/") for s in resolved.policy)


def test_methodology_ids_cannot_inject_policy_or_unknown() -> None:
    resolved = resolve_skills_for_node(
        "art",
        hints={"methodology_ids": ["policy/playtest", "billing/usage", "art/hud-design"]},
    )
    ids = [s.id for s in resolved.methodology]
    assert "policy/playtest" not in ids
    assert "billing/usage" not in ids
    assert ids == ["art/hud-design"]


@pytest.mark.asyncio
async def test_llm_select_parses_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "skills_llm_selection", True)

    async def complete(_system: str, _user: str) -> str:
        return '{"skill_ids":["art/pixel-art","policy/playtest","nope"]}'

    resolved = await resolve_skills_for_node_async(
        "art", hints={"style": "像素"}, complete=complete
    )
    ids = [s.id for s in resolved.methodology]
    assert ids == ["art/pixel-art"]
    assert all(not s.id.startswith("policy/") for s in resolved.methodology)
    assert any(s.id.startswith("policy/") for s in resolved.policy)


@pytest.mark.asyncio
async def test_llm_select_falls_back_on_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "skills_llm_selection", True)

    async def complete(_system: str, _user: str) -> str:
        return "not-json"

    resolved = await resolve_skills_for_node_async(
        "art", hints={"style": "像素 HUD"}, complete=complete
    )
    # 回落确定性：像素 → pixel-art
    ids = [s.id for s in resolved.methodology]
    assert "art/pixel-art" in ids


def test_offline_eval_deterministic_precision_on_fixtures() -> None:
    """轻量 offline eval：委托完整套件（见 test_skills_offline_eval）。"""
    from app.forge.skills.offline_eval import EVAL_FIXTURES, evaluate_routing

    report = evaluate_routing(EVAL_FIXTURES)
    assert report.precision_at_1 >= 0.95
    assert report.expected_hit_rate >= 0.95


@pytest.mark.asyncio
async def test_select_methodology_ids_via_llm_unit() -> None:
    from app.forge.skills.catalog import list_skill_metas

    cands = [m for m in list_skill_metas() if m.kind == "methodology" and "art" in m.nodes]

    async def complete(_s: str, _u: str) -> str:
        return '{"skill_ids":["art/visual-composition"]}'

    ids = await select_methodology_ids_via_llm(
        node="art", candidates=cands, hints={}, complete=complete
    )
    assert ids == ["art/visual-composition"]
