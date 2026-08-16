"""PLAN_PROMPT build_routing 选型指南测试。"""

from app.forge.prompts import PLAN_PROMPT, PLAN_REVISE_PROMPT


def test_plan_prompt_includes_build_routing_guidance() -> None:
    assert "build_routing" in PLAN_PROMPT
    assert 'build="none"' in PLAN_PROMPT
    assert 'build="vite"' in PLAN_PROMPT
    assert "matter-js" in PLAN_PROMPT


def test_plan_revise_prompt_mentions_build_routing() -> None:
    assert "build_routing" in PLAN_REVISE_PROMPT
