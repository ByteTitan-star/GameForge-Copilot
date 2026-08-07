"""langfuse trace 集成（docs/02 §可观测）。

未配置 LANGFUSE_* key 时 client 禁用，调用为空操作，不影响单测/本地。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import settings


def _enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


@contextmanager
def observe_run(run_id: str, name: str = "generation_run") -> Iterator[Any]:
    """包一层 generation_run span；无 key 时 yield None。"""
    if not _enabled():
        yield None
        return
    from langfuse import get_client

    client = get_client()
    with client.start_as_current_observation(
        as_type="span",
        name=name,
        metadata={"run_id": run_id},
    ) as span:
        yield span


@contextmanager
def observe_phase(phase: str) -> Iterator[Any]:
    if not _enabled():
        yield None
        return
    from langfuse import get_client

    client = get_client()
    with client.start_as_current_observation(as_type="span", name=f"phase:{phase}") as span:
        yield span
