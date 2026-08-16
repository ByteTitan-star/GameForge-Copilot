"""Sandbox 对照 dry-run（默认 local）；live E2B 仅显式环境变量。

绝不修改生产默认 backend。
"""

from __future__ import annotations

import os
import statistics
import time
from typing import Any

from app.sandbox.local import LocalSandbox


async def run_benchmark(rounds: int = 5) -> dict[str, Any]:
    local = await _time_local(rounds=rounds)
    live = await _maybe_live_e2b(rounds=min(rounds, 3))
    return {
        "production_default_must_remain": "docker",
        "local_dry_run": local,
        "e2b_live": live,
    }


async def _time_local(*, rounds: int) -> dict[str, Any]:
    backend = LocalSandbox()
    create_ms: list[float] = []
    exec_ms: list[float] = []
    html = "<!DOCTYPE html><html><body>ok</body></html>"
    for _ in range(rounds):
        t0 = time.perf_counter()
        session = await backend.create(tier="standard")
        create_ms.append((time.perf_counter() - t0) * 1000)
        t1 = time.perf_counter()
        result = await backend.execute(session, source={"index.html": html})
        exec_ms.append((time.perf_counter() - t1) * 1000)
        await backend.destroy(session)
        if not result.ok:
            raise RuntimeError(result.error or "sandbox execute failed")
    return {
        "backend": "local",
        "rounds": rounds,
        "create_ms_p50": statistics.median(create_ms),
        "create_ms_p95": _p95(create_ms),
        "exec_ms_p50": statistics.median(exec_ms),
        "exec_ms_p95": _p95(exec_ms),
        "note": "local dry-run only; not a Docker/E2B production Go signal",
    }


async def _maybe_live_e2b(rounds: int) -> dict[str, Any] | None:
    if os.environ.get("E2B_BENCHMARK_LIVE", "").lower() not in {"1", "true", "yes"}:
        return None
    from app.core.config import settings

    if not settings.sandbox_e2b_enabled or not settings.e2b_api_key:
        return {
            "backend": "e2b",
            "skipped": True,
            "reason": "requires sandbox_e2b_enabled + E2B_API_KEY",
        }
    from app.sandbox.e2b import E2BSandbox

    backend = E2BSandbox()
    create_ms: list[float] = []
    exec_ms: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        session = await backend.create(tier="standard")
        create_ms.append((time.perf_counter() - t0) * 1000)
        t1 = time.perf_counter()
        result = await backend.execute(
            session, source={"index.html": "<!DOCTYPE html><html></html>"}
        )
        exec_ms.append((time.perf_counter() - t1) * 1000)
        await backend.destroy(session)
        if not result.ok:
            raise RuntimeError(result.error or "e2b execute failed")
    return {
        "backend": "e2b",
        "rounds": rounds,
        "create_ms_p50": statistics.median(create_ms),
        "create_ms_p95": _p95(create_ms),
        "exec_ms_p50": statistics.median(exec_ms),
        "exec_ms_p95": _p95(exec_ms),
        "note": "live PoC only; do not flip production sandbox_backend",
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[idx]
