"""Langfuse trace 集成（docs/02 §可观测）：run/phase/subsystem span 包装。

client 访问与生命周期统一在 app.core.langfuse；此处仅保留 forge 编排语义命名，
供 graph.py 用 observe_run / observe_phase。未配置 key 时为空操作。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.langfuse import observe_span, propagate_trace_attrs


@contextmanager
def observe_run(
    run_id: str,
    name: str = "generation_run",
    *,
    user_id: str | None = None,
    game_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any]:
    """包一层 generation_run span，并 propagate session_id=game_id / user_id / tags。"""
    uniq_tags: list[str] = []
    seen: set[str] = set()
    for t in ["forge", *(tags or [])]:
        if t not in seen:
            seen.add(t)
            uniq_tags.append(t)
    meta: dict[str, Any] = {"run_id": run_id}
    if user_id is not None:
        meta["user_id"] = user_id
    if game_id is not None:
        meta["game_id"] = game_id
    with (
        observe_span(name, metadata=meta) as span,
        propagate_trace_attrs(
            user_id=user_id,
            session_id=game_id,
            tags=uniq_tags,
            metadata={"run_id": run_id},
        ),
    ):
        yield span


@contextmanager
def observe_phase(phase: str) -> Iterator[Any]:
    with (
        observe_span(f"phase:{phase}") as span,
        propagate_trace_attrs(tags=["forge", f"phase:{phase}"]),
    ):
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
