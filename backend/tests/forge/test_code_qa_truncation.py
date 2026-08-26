"""CodeQa / Vite 截断路径集成测试（mock LLM）。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import settings
from app.forge.build.code_output import ParsedCodeOutput
from app.forge.build.integration import run_project_build_loop
from app.forge.build.routing import BuildRouting
from app.forge.llm_continuation import OUTPUT_TRUNCATED_ERROR, OutputTruncatedError
from app.forge.subgraphs.code_qa_loop import after_code_or_repair, build_code_qa_loop


@pytest.mark.asyncio
async def test_run_project_build_loop_handles_output_truncated() -> None:
    routing = BuildRouting(build="vite", renderer="canvas", ui="vanilla", dependencies=[])
    initial = ParsedCodeOutput(
        format="project",
        files={"src/main.ts": "broken"},
        routing=routing,
    )

    async def repair_fn(_current: ParsedCodeOutput, _err: str) -> ParsedCodeOutput:
        raise OutputTruncatedError()

    result = await run_project_build_loop(initial, repair_fn=repair_fn, max_retries=2)
    assert result.ok is False
    assert result.output_truncated is True


@pytest.mark.asyncio
async def test_code_qa_loop_skips_diagnose_on_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "code_qa_max_attempts", 3)
    steps: list[str] = []

    async def code_or_repair(state: dict[str, Any]) -> dict[str, Any]:
        steps.append("code")
        attempt = int(state.get("attempt") or 0) + 1
        if attempt == 1:
            return {
                "attempt": attempt,
                "candidate_ready": False,
                "playtest_errors": [OUTPUT_TRUNCATED_ERROR],
            }
        return {
            "attempt": attempt,
            "candidate_ready": True,
            "candidate_version": attempt,
            "qa_ok": False,
            "playtest_errors": [],
        }

    async def playtest(state: dict[str, Any]) -> dict[str, Any]:
        steps.append("playtest")
        return {
            "qa_ok": True,
            "attempt": state.get("attempt"),
            "candidate_version": state.get("candidate_version"),
            "candidate_ready": True,
        }

    async def diagnose(state: dict[str, Any]) -> dict[str, Any]:
        steps.append("diagnose")
        return {"attempt": state.get("attempt")}

    graph = build_code_qa_loop(
        code_or_repair=code_or_repair,
        playtest=playtest,
        diagnose=diagnose,
    )
    result = await graph.ainvoke({"attempt": 0})
    assert result.get("qa_ok") is True
    assert "diagnose" not in steps
    assert steps == ["code", "code", "playtest"]


def test_after_code_or_repair_routes_truncation_to_retry() -> None:
    assert (
        after_code_or_repair(
            {
                "candidate_ready": False,
                "attempt": 1,
                "playtest_errors": [OUTPUT_TRUNCATED_ERROR],
            }
        )
        == "retry"
    )


def test_after_code_or_repair_truncation_exhausted() -> None:
    assert (
        after_code_or_repair(
            {
                "candidate_ready": False,
                "attempt": 3,
                "playtest_errors": [OUTPUT_TRUNCATED_ERROR],
            }
        )
        == "exhausted"
    )


@pytest.mark.asyncio
async def test_execute_code_or_repair_returns_truncation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.forge import code_qa_exec as cqe
    from app.forge.memory.context_builder import BuiltContext

    async def fake_code_llm(*_a, **_k) -> tuple[str, bool]:
        return "<html>", True

    async def fake_build_node_context(*_a, **_k) -> BuiltContext:
        return BuiltContext(
            user_message="请实现游戏",
            sections={},
            token_estimate=10,
            node="code",
        )

    monkeypatch.setattr(cqe, "_code_llm", fake_code_llm)
    monkeypatch.setattr(
        "app.forge.memory.loader.build_node_context",
        fake_build_node_context,
    )
    monkeypatch.setattr(settings, "memory_session_summary", False)
    monkeypatch.setattr(settings, "build_pipeline_enabled", False)

    ctx = SimpleNamespace(
        s=None,
        r=None,
        game=SimpleNamespace(id="g1", title="Test", owner_id="u1", current_version=0),
        run=SimpleNamespace(
            id="r1",
            user_id="u1",
            llm_config_id=None,
            status="running",
            ended_at=None,
            phase="code",
        ),
    )

    design_doc = {
        "title": "Test",
        "engine": {"id": "canvas"},
        "format_version": "2.0",
        "core_loop": "test",
        "controls": [],
        "entities": [],
        "levels": [],
        "acceptance_criteria": [],
    }

    async def noop(*_a, **_k):
        return "ok"

    async def check_ctrl_ok(*_a, **_k):
        return "ok"

    result = await cqe.execute_code_or_repair(
        ctx,
        {"attempt": 0, "design_doc": design_doc, "artifacts": [], "art_direction": {}},
        streamed_llm=noop,
        set_phase=noop,
        check_ctrl=check_ctrl_ok,
        normalize_html=lambda x: x,
        commit_project_build=noop,
        commit_native_build=noop,
        run_finalized_exc=RuntimeError,
    )
    assert result.get("candidate_ready") is False
    assert OUTPUT_TRUNCATED_ERROR in (result.get("playtest_errors") or [])
    assert result.get("failure_kind") == "truncated"
