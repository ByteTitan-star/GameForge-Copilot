"""P2：routed code/repair prompts 不全量注入 Skill。"""

from __future__ import annotations

from app.forge.prompts import build_code_prompt, build_repair_prompt
from app.forge.skills.catalog import list_skill_metas


def test_build_code_prompt_loads_selected_engine_only(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_code_prompt("phaser3")
    assert "phaser" in prompt.lower() or "Phaser" in prompt
    # 不应把全部 methodology 正文塞进同一 prompt
    assert prompt.count("【Skill:") <= 2
    assert "policy/playtest" in prompt or "Playwright" in prompt
    assert len(list_skill_metas()) > 5


def test_build_repair_prompt_includes_repair_methodology(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_repair_prompt("canvas")
    assert "runtime" in prompt.lower() or "回归" in prompt
    assert "Playwright" in prompt or "试玩" in prompt
