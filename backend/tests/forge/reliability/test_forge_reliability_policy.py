"""P0：NodeExecutionPolicy 与 LLM 超时对齐。"""

from __future__ import annotations

from app.core.config import settings
from app.forge.reliability.policy import (
    NODE_EXECUTION_POLICIES,
    resolve_node_run_timeout,
)


def test_policies_cover_core_nodes() -> None:
    for name in ("plan", "art", "code_or_repair", "playtest", "diagnose", "code_qa_loop"):
        assert name in NODE_EXECUTION_POLICIES


def test_llm_nodes_timeout_exceeds_llm_request_timeout() -> None:
    llm = settings.llm_request_timeout
    for name in ("plan", "art", "code_or_repair", "diagnose"):
        assert resolve_node_run_timeout(name) > llm


def test_entry_router_fixed_short_timeout() -> None:
    assert resolve_node_run_timeout("entry_router") == 10.0


def test_playtest_timeout_independent_of_llm() -> None:
    assert resolve_node_run_timeout("playtest") == 180.0
