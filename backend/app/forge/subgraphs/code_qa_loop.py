"""CodeQaLoop：code ↔ playtest ↔ diagnose 有界子图。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.sandbox.playtest import is_permanent_infra_error

NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class CodeQaLoopState(TypedDict, total=False):
    design_doc: dict[str, Any] | str
    art_options: dict[str, Any]
    art_direction: dict[str, Any]
    artifacts: list[dict[str, str]]
    entry_requirement: str | None
    attempt: int
    qa_ok: bool
    exhausted: bool
    candidate_version: int | None
    candidate_ready: bool
    candidate_kind: str | None
    playtest_errors: list[str]
    console_logs: list[str]
    failure_kind: str | None
    qa_diagnosis: str
    motion_signal: str | None
    paused: bool
    failed: bool
    hitl_stop: bool
    code_qa_reset: bool


def _max_attempts() -> int:
    return int(settings.code_qa_max_attempts)


def after_code_or_repair(
    state: CodeQaLoopState,
) -> Literal["playtest", "diagnose", "exhausted", "__end__"]:
    if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
        return "__end__"
    if state.get("candidate_ready"):
        return "playtest"
    attempt = int(state.get("attempt") or 0)
    if attempt >= _max_attempts():
        return "exhausted"
    # build fail → diagnose（infra 不会从 code_or_repair 产生）
    return "diagnose"


def after_playtest(
    state: CodeQaLoopState,
) -> Literal["ok", "exhausted", "replay", "diagnose", "__end__"]:
    if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
        return "__end__"
    if state.get("qa_ok"):
        return "ok"
    attempt = int(state.get("attempt") or 0)
    if attempt >= _max_attempts():
        return "exhausted"
    if state.get("failure_kind") == "infra":
        # Playwright/Chromium 缺失等环境问题：空转重试无意义，立即耗尽
        if is_permanent_infra_error(list(state.get("playtest_errors") or [])):
            return "exhausted"
        return "replay"
    return "diagnose"


def after_diagnose(
    state: CodeQaLoopState,
) -> Literal["code_or_repair", "__end__"]:
    if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
        return "__end__"
    return "code_or_repair"


def build_code_qa_loop(
    *,
    code_or_repair: NodeFn,
    playtest: NodeFn,
    diagnose: NodeFn,
) -> Any:
    """编译 CodeQaLoop 子图。节点禁止写 run.status / 调用 _fail。"""

    async def infra_replay(state: CodeQaLoopState) -> dict[str, Any]:
        """infra：只加 attempt，保持同一 candidate，回到 playtest。"""
        return {
            "attempt": int(state.get("attempt") or 0) + 1,
            "qa_ok": False,
            "exhausted": False,
        }

    async def mark_ok(state: CodeQaLoopState) -> dict[str, Any]:
        return {"qa_ok": True, "exhausted": False}

    async def mark_exhausted(state: CodeQaLoopState) -> dict[str, Any]:
        return {
            "qa_ok": False,
            "exhausted": True,
            "candidate_ready": False,
        }

    g = StateGraph(CodeQaLoopState)
    g.add_node("code_or_repair", code_or_repair)  # type: ignore[call-overload]
    g.add_node("playtest", playtest)  # type: ignore[call-overload]
    g.add_node("diagnose", diagnose)  # type: ignore[call-overload]
    g.add_node("infra_replay", infra_replay)
    g.add_node("mark_ok", mark_ok)
    g.add_node("mark_exhausted", mark_exhausted)

    g.add_edge(START, "code_or_repair")
    g.add_conditional_edges(
        "code_or_repair",
        after_code_or_repair,
        {
            "playtest": "playtest",
            "diagnose": "diagnose",
            "exhausted": "mark_exhausted",
            END: END,
        },
    )
    g.add_conditional_edges(
        "playtest",
        after_playtest,
        {
            "ok": "mark_ok",
            "exhausted": "mark_exhausted",
            "replay": "infra_replay",
            "diagnose": "diagnose",
            END: END,
        },
    )
    g.add_edge("infra_replay", "playtest")
    g.add_conditional_edges(
        "diagnose",
        after_diagnose,
        {"code_or_repair": "code_or_repair", END: END},
    )
    g.add_edge("mark_ok", END)
    g.add_edge("mark_exhausted", END)
    return g.compile()
