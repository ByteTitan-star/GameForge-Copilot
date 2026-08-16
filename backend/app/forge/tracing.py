"""Langfuse trace 集成（docs/02 §可观测）：run/phase/subsystem span 包装。

client 访问与生命周期统一在 app.core.langfuse；此处仅保留 forge 编排语义命名，
供 graph.py 用 observe_run / observe_phase。未配置 key 时为空操作。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.langfuse import observe_span


@contextmanager
def observe_run(run_id: str, name: str = "generation_run") -> Iterator[Any]:
    """包一层 generation_run span；无 key 时 yield None。"""
    with observe_span(name, metadata={"run_id": run_id}) as span:
        yield span


@contextmanager
def observe_phase(phase: str) -> Iterator[Any]:
    with observe_span(f"phase:{phase}") as span:
        yield span


@contextmanager
def observe_context_build(
    *,
    node: str,
    token_estimate: int,
    fingerprint: str,
    section_lens: dict[str, int] | None = None,
) -> Iterator[Any]:
    """P5：ContextBuilder 拼装 span（fingerprint / token / section 长度）。"""
    meta: dict[str, Any] = {
        "node": node,
        "token_estimate": token_estimate,
        "fingerprint": fingerprint,
    }
    if section_lens:
        meta["section_lens"] = section_lens
    with observe_span("context_build", metadata=meta) as span:
        yield span


@contextmanager
def observe_subsystem(
    kind: str, name: str, metadata: dict[str, Any] | None = None
) -> Iterator[Any]:
    """P5：Memory / Skill / Sandbox / Cache 子系统 span。"""
    meta = {"subsystem": kind, **(metadata or {})}
    with observe_span(f"{kind}:{name}", metadata=meta) as span:
        yield span
