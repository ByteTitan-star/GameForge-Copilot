"""CodeQaLoop native diagnose branch tests."""

from __future__ import annotations

import pytest

from app.forge.code_qa_exec import execute_diagnose


class _FakeGame:
    title = "test"
    owner_id = "00000000-0000-0000-0000-000000000001"


class _FakeCtx:
    game = _FakeGame()


@pytest.mark.asyncio
async def test_execute_diagnose_uses_native_structured_context(monkeypatch) -> None:
    async def _noop_llm(_ctx, _system, _user) -> str:
        raise AssertionError("LLM should not be called for native diagnostic path")

    state = {
        "design_doc": {"title": "t", "engine": {"id": "godot4"}},
        "playtest_errors": ["BUILD_FAILED"],
        "console_logs": ["err"],
        "failure_kind": "build",
        "native_structured_diagnostic": {
            "engine": "godot",
            "phase": "build",
            "error_type": "BUILD_FAILED",
            "exit_code": None,
            "summary": "import failed",
            "stderr_excerpt": "parse error",
            "affected_files": [],
            "retryable": True,
            "engine_version": "4.3",
        },
    }
    out = await execute_diagnose(_FakeCtx(), state, llm=_noop_llm)
    assert "Native Engine Structured Diagnostic" in out["qa_diagnosis"]
    assert "BUILD_FAILED" in out["qa_diagnosis"]
    assert out["qa_ok"] is False
