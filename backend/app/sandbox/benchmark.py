"""Sandbox 对照 dry-run（默认 local）；live Daytona 仅显式环境变量。

绝不修改生产默认 backend。
"""

from __future__ import annotations

import os
import statistics
import time
from typing import Any

from app.sandbox.local import LocalSandbox


async def run_benchmark(rounds: int = 5) -> dict[str, Any]:
    """运行 sandbox 对照基准测试（local dry-run + 可选 live Daytona）。

    场景：运维/开发评估沙箱创建与执行耗时，不修改生产默认 backend。
    参数：rounds - 本地基准轮次。
    返回：含 local_dry_run 与 daytona_live（未启用时为 None）的统计 dict。
    """
    local = await _time_local(rounds=rounds)
    live = await _maybe_live_daytona(rounds=min(rounds, 3))
    return {
        "production_default_must_remain": "docker",
        "local_dry_run": local,
        "daytona_live": live,
    }


async def _time_local(*, rounds: int) -> dict[str, Any]:
    """测量 LocalSandbox create/execute/destroy 的 p50/p95 耗时。

    场景：run_benchmark 本地对照组。
    参数：rounds - 重复轮次。
    返回：含 create_ms_p50/p95、exec_ms_p50/p95 的统计 dict。
    """
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
        "note": "local dry-run only; not a Docker/Daytona production Go signal",
    }


async def _maybe_live_daytona(rounds: int) -> dict[str, Any] | None:
    """在显式开启 DAYTONA_BENCHMARK_LIVE 时测量真实 Daytona 耗时。

    场景：run_benchmark 可选 live 对照；未开 flag 或缺配置时跳过。
    参数：rounds - live 基准轮次（上限由调用方裁剪）。
    返回：统计 dict、skipped 说明，或 None（未启用 live）。
    """
    if os.environ.get("DAYTONA_BENCHMARK_LIVE", "").lower() not in {"1", "true", "yes"}:
        return None
    from app.core.config import settings

    if not settings.sandbox_daytona_enabled or not settings.daytona_api_key:
        return {
            "backend": "daytona",
            "skipped": True,
            "reason": "requires sandbox_daytona_enabled + DAYTONA_API_KEY",
        }
    from app.sandbox.daytona import DaytonaSandbox

    backend = DaytonaSandbox()
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
            raise RuntimeError(result.error or "daytona execute failed")
    return {
        "backend": "daytona",
        "rounds": rounds,
        "create_ms_p50": statistics.median(create_ms),
        "create_ms_p95": _p95(create_ms),
        "exec_ms_p50": statistics.median(exec_ms),
        "exec_ms_p95": _p95(exec_ms),
        "note": "live PoC only; do not flip production sandbox_backend casually",
    }


def _p95(values: list[float]) -> float:
    """计算样本的近似 95 分位值。

    场景：benchmark 汇总 create/exec 耗时。
    参数：values - 毫秒耗时列表。
    返回：排序后第 95 百分位元素；空列表返回 0.0。
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[idx]
