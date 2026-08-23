"""acceptance_criteria 运行时探针单元测试。"""

from __future__ import annotations

import pytest

from app.sandbox.acceptance_runtime import (
    RuntimeProbe,
    extract_target_state,
    parse_runtime_probes,
    runtime_probe_errors,
    source_only_probe_errors,
    state_matches,
    state_observed,
)


def test_extract_target_state_from_enter_phrase() -> None:
    assert extract_target_state("点击开始进入 playing") == "playing"
    assert extract_target_state("达分进入 level_complete") == "level_complete"
    assert extract_target_state("结算后返回 menu") == "menu"


def test_state_aliases() -> None:
    assert state_matches("start", "menu")
    assert state_matches("play", "playing")
    assert state_observed({"menu", "boot"}, "menu")


def test_parse_runtime_probes() -> None:
    doc = {
        "title": "t",
        "acceptance_criteria": [
            {"id": "AC-01", "requirement": "开始", "verification": "点击开始进入 playing"},
            {"id": "AC-02", "requirement": "通关", "verification": "达分进入 level_complete"},
            {"id": "AC-03", "requirement": "暂停", "verification": "暂停后继续正常运行"},
            {"id": "AC-04", "requirement": "无错", "verification": "试玩无 pageerror"},
        ],
    }
    probes = parse_runtime_probes(doc)
    kinds = {p.criterion_id: p for p in probes}
    assert kinds["AC-01"].kind == "after_start"
    assert kinds["AC-01"].target_state == "playing"
    assert kinds["AC-02"].kind == "terminal_state"
    assert kinds["AC-03"].kind == "pause_resume"
    assert "AC-04" not in kinds


def test_source_only_probe_requires_state_token_in_html() -> None:
    probes = [
        RuntimeProbe("AC-02", "level_complete", "terminal_state", "达分进入 level_complete"),
    ]
    bad = source_only_probe_errors("<html><script>state='playing'</script></html>", probes)
    assert bad
    good = source_only_probe_errors(
        "<html><script>setScreen('level_complete')</script></html>", probes
    )
    assert good == []


def test_runtime_probe_after_start() -> None:
    probes = [RuntimeProbe("AC-01", "playing", "after_start", "点击开始进入 playing")]
    errs = runtime_probe_errors(active_state="menu", observed_states=["menu"], probes=probes)
    assert errs
    assert any("AC-01" in e for e in errs)
    assert (
        runtime_probe_errors(active_state="playing", observed_states=["playing"], probes=probes)
        == []
    )


@pytest.mark.asyncio
async def test_run_runtime_acceptance_with_fake_page() -> None:
    from app.sandbox.acceptance_runtime import run_runtime_acceptance

    class _FakePage:
        async def evaluate(self, _js: str) -> dict[str, object]:
            return {"active": "playing", "states": ["menu", "playing"]}

    doc = {
        "title": "t",
        "acceptance_criteria": [
            {"id": "AC-01", "requirement": "开始", "verification": "点击开始进入 playing"},
            {"id": "AC-02", "requirement": "失败", "verification": "撞障碍进入 game_over"},
        ],
    }
    errs = await run_runtime_acceptance(_FakePage(), doc, html="<script>game_over</script>")
    assert not any("AC-01" in e for e in errs)
    assert not any("game_over" in e for e in errs)


@pytest.mark.asyncio
async def test_terminal_cheat_probe_verifies_state() -> None:
    from app.sandbox.acceptance_runtime import (
        CHEAT_AVAILABLE_JS,
        INVOKE_SET_STATE_JS,
        READ_RUNTIME_STATE_JS,
        required_cheat_state_errors,
        terminal_cheat_probe_errors,
    )

    class _CheatPage:
        def __init__(self) -> None:
            self.state = "playing"

        async def evaluate(self, js: str, arg: object | None = None) -> object:
            if js == CHEAT_AVAILABLE_JS:
                return True
            if js == READ_RUNTIME_STATE_JS:
                return {"active": self.state, "states": [self.state]}
            if js == INVOKE_SET_STATE_JS and arg == "game_over":
                self.state = "game_over"
                return {"available": True, "invoked": "setState"}
            return {"available": False, "invoked": None}

        async def wait_for_timeout(self, _ms: int) -> None:
            return None

    class _CheatPageBroken(_CheatPage):
        async def evaluate(self, js: str, arg: object | None = None) -> object:
            if js == INVOKE_SET_STATE_JS:
                return {"available": True, "invoked": "gameOver"}
            return await super().evaluate(js, arg)

    probes = [
        RuntimeProbe("AC-05", "game_over", "terminal_state", "撞障碍进入 game_over"),
    ]
    page = _CheatPage()
    assert await terminal_cheat_probe_errors(page, probes) == []

    doc = {
        "title": "t",
        "game_states": [{"id": "playing"}, {"id": "game_over"}],
    }
    assert await required_cheat_state_errors(page, doc) == []

    errs = await terminal_cheat_probe_errors(_CheatPageBroken(), probes)
    assert errs
    assert any("AC-05" in e for e in errs)
