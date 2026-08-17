"""P2：routed code/repair prompts 不全量注入 Skill。"""

from __future__ import annotations

from app.forge.prompts import ART_OPTIONS_PROMPT, build_code_prompt, build_repair_prompt
from app.forge.skills.catalog import list_skill_metas


def test_art_options_prompt_forbids_default_cyber_pair() -> None:
    assert "赛博霓虹" in ART_OPTIONS_PROMPT
    assert "极简矢量" in ART_OPTIONS_PROMPT
    assert "缺省组合" in ART_OPTIONS_PROMPT


def test_build_code_prompt_loads_selected_engine_only(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_code_prompt("phaser3")
    assert "phaser" in prompt.lower() or "Phaser" in prompt
    assert prompt.count("【Skill:") <= 2
    assert "policy/playtest" in prompt or "Playwright" in prompt
    assert len(list_skill_metas()) > 5


def test_build_repair_prompt_includes_repair_methodology(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_repair_prompt("canvas")
    assert "runtime" in prompt.lower() or "回归" in prompt
    assert "Playwright" in prompt or "试玩" in prompt
