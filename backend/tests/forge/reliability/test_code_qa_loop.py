"""CodeQaLoop 子图路由单测（全 mock）。"""

from __future__ import annotations

from typing import Any

import pytest
from app.core.config import settings
from app.forge.subgraphs.code_qa_loop import (
    after_code_or_repair,
    after_playtest,
    build_code_qa_loop,
)


@pytest.mark.asyncio
async def test_infra_failure_retries_same_candidate_without_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "code_qa_max_attempts", 3)
    repair_calls = {"n": 0}
    playtest_calls = {"n": 0}
    candidate_versions: list[int | None] = []

    async def code_or_repair(state: dict[str, Any]) -> dict[str, Any]:
        repair_calls["n"] += 1
        attempt = int(state.get("attempt") or 0) + 1
        return {
            "attempt": attempt,
            "candidate_ready": True,
            "candidate_version": 10,
            "failure_kind": None,
            "qa_ok": False,
        }

    async def playtest(state: dict[str, Any]) -> dict[str, Any]:
        playtest_calls["n"] += 1
        candidate_versions.append(state.get("candidate_version"))
        return {
            "qa_ok": False,
            "failure_kind": "infra",
            "playtest_errors": ["PLAYWRIGHT_UNAVAILABLE"],
            "attempt": state.get("attempt"),
            "candidate_version": state.get("candidate_version"),
            "candidate_ready": True,
        }

    async def diagnose(state: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("infra must not diagnose")

    graph = build_code_qa_loop(
        code_or_repair=code_or_repair,
        playtest=playtest,
        diagnose=diagnose,
    )
    result = await graph.ainvoke({"attempt": 0, "design_doc": {}})

    assert result.get("exhausted") is True
    assert result.get("qa_ok") is False
    assert repair_calls["n"] == 1
    assert playtest_calls["n"] == 3
    assert candidate_versions == [10, 10, 10]


@pytest.mark.asyncio
async def test_product_fail_diagnose_then_repair_then_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "code_qa_max_attempts", 3)
    steps: list[str] = []

    async def code_or_repair(state: dict[str, Any]) -> dict[str, Any]:
        steps.append("code")
        attempt = int(state.get("attempt") or 0) + 1
        return {
            "attempt": attempt,
            "candidate_ready": True,
            "candidate_version": attempt,
            "qa_ok": False,
        }

    async def playtest(state: dict[str, Any]) -> dict[str, Any]:
        steps.append("playtest")
        attempt = int(state.get("attempt") or 0)
        if attempt >= 2:
            return {
                "qa_ok": True,
                "attempt": attempt,
                "candidate_version": state.get("candidate_version"),
                "candidate_ready": True,
                "failure_kind": None,
                "motion_signal": "raf",
            }
        return {
            "qa_ok": False,
            "failure_kind": "product",
            "playtest_errors": ["pageerror"],
            "attempt": attempt,
            "candidate_version": state.get("candidate_version"),
            "candidate_ready": True,
        }

    async def diagnose(state: dict[str, Any]) -> dict[str, Any]:
        steps.append("diagnose")
        return {
            "qa_diagnosis": '{"summary":"fix"}',
            "candidate_ready": False,
            "attempt": state.get("attempt"),
            "playtest_errors": state.get("playtest_errors") or [],
        }

    graph = build_code_qa_loop(
        code_or_repair=code_or_repair,
        playtest=playtest,
        diagnose=diagnose,
    )
    result = await graph.ainvoke({"attempt": 0})

    assert result.get("qa_ok") is True
    assert result.get("exhausted") is False
    assert steps == ["code", "playtest", "diagnose", "code", "playtest"]


@pytest.mark.asyncio
async def test_exhausted_after_three_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "code_qa_max_attempts", 3)

    async def code_or_repair(state: dict[str, Any]) -> dict[str, Any]:
        attempt = int(state.get("attempt") or 0) + 1
        return {
            "attempt": attempt,
            "candidate_ready": True,
            "candidate_version": attempt,
            "qa_ok": False,
        }

    async def playtest(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "qa_ok": False,
            "failure_kind": "product",
            "playtest_errors": ["still broken"],
            "attempt": state.get("attempt"),
            "candidate_version": state.get("candidate_version"),
            "candidate_ready": True,
        }

    async def diagnose(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "qa_diagnosis": "x",
            "candidate_ready": False,
            "attempt": state.get("attempt"),
        }

    graph = build_code_qa_loop(
        code_or_repair=code_or_repair,
        playtest=playtest,
        diagnose=diagnose,
    )
    result = await graph.ainvoke({"attempt": 0})
    assert result.get("exhausted") is True
    assert result.get("qa_ok") is False
    assert int(result.get("attempt") or 0) == 3


def test_after_playtest_routing_helpers() -> None:
    assert after_playtest({"qa_ok": True}) == "ok"
    assert after_playtest({"qa_ok": False, "attempt": 3}) == "exhausted"
    assert after_playtest({"qa_ok": False, "attempt": 1, "failure_kind": "infra"}) == "replay"
    assert after_playtest({"qa_ok": False, "attempt": 1, "failure_kind": "product"}) == "diagnose"
    assert after_code_or_repair({"candidate_ready": True}) == "playtest"
    assert after_code_or_repair({"candidate_ready": False, "attempt": 1}) == "diagnose"
