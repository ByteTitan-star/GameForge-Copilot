"""P3.3：sandbox tier 推荐与进程内 telemetry。

原则（计划原文）：以 telemetry 为准，避免为省几十 MB 过度调度。
默认不自动选档；开启后优先升级（OOM/超时/大体量），仅在强信号下降到 lite。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

KNOWN_TIERS = ("lite", "standard", "heavy")
_HEAVY_ENGINES = frozenset({"vite", "phaser3", "pixi", "pixijs", "three", "threejs"})
_LITE_ENGINES = frozenset({"canvas", "vanilla", "html"})
_UPGRADE_MARKERS = ("oom", "out of memory", "超时", "timeout", "killed", "memory")

# 进程内环形缓冲：供同进程后续 create 参考（非跨实例 SoT）
_OUTCOMES: deque[tuple[str, bool, str]] = deque(maxlen=64)


@dataclass(frozen=True)
class TierSignals:
    source: dict[str, str] | None = None
    hints: dict[str, Any] | None = field(default=None)


def clear_tier_telemetry_for_tests() -> None:
    _OUTCOMES.clear()


def record_sandbox_outcome(
    *,
    tier: str,
    ok: bool,
    error: str | None = None,
    backend: str | None = None,
) -> None:
    """记录一次执行结果；供 recommend_tier 与 Prometheus 使用。"""
    err = (error or "").strip()
    _OUTCOMES.append((tier or "standard", bool(ok), err.lower()))
    try:
        from app.core.metrics import SANDBOX_TIER_RUNS

        status = "ok" if ok else "fail"
        SANDBOX_TIER_RUNS.labels(backend or "unknown", tier or "standard", status).inc()
    except Exception:  # noqa: BLE001 — metrics 不可用时不影响主路径
        pass


def recommend_tier(signals: TierSignals | None = None) -> str:
    """根据信号与近期失败推荐档位；始终返回 KNOWN_TIERS 之一。"""
    signals = signals or TierSignals()
    base = _normalize(settings.sandbox_default_tier)
    if _recent_resource_pressure():
        return "heavy"

    source_bytes = _source_bytes(signals.source)
    file_count = len(signals.source or {})
    engine = str((signals.hints or {}).get("engine_id") or "").strip().lower()

    if source_bytes >= 500_000 or file_count >= 30 or engine in _HEAVY_ENGINES:
        return "heavy"

    if (
        engine in _LITE_ENGINES
        and source_bytes <= 32_000
        and file_count <= 5
        and not _recent_resource_pressure()
    ):
        return "lite"

    return base


def tier_hints_from_design_doc(design_doc: dict[str, Any] | None) -> dict[str, Any]:
    """从 design_doc 提取 sandbox tier 提示（engine_id）。"""
    if not design_doc:
        return {}
    engine = design_doc.get("engine")
    if isinstance(engine, dict):
        engine_id = str(engine.get("id") or "").strip()
    else:
        engine_id = str(engine or "").strip()
    if not engine_id:
        return {}
    return {"engine_id": engine_id}


def resolve_create_tier(
    *,
    source: dict[str, str] | None = None,
    hints: dict[str, Any] | None = None,
    explicit: str | None = None,
) -> str | None:
    """OneShot/create 入口：flag 关返回 explicit（可 None）；开则推荐。"""
    if explicit:
        return _normalize(explicit)
    if not settings.sandbox_tier_auto:
        return None
    return recommend_tier(TierSignals(source=source, hints=hints))


def _recent_resource_pressure() -> bool:
    if not _OUTCOMES:
        return False
    window = list(_OUTCOMES)[-16:]
    hits = 0
    for _tier, ok, err in window:
        if ok:
            continue
        if any(m in err for m in _UPGRADE_MARKERS):
            hits += 1
    return hits >= 1


def _source_bytes(source: dict[str, str] | None) -> int:
    if not source:
        return 0
    return sum(len(v.encode("utf-8")) for v in source.values())


def _normalize(tier: str | None) -> str:
    key = (tier or "standard").strip().lower()
    return key if key in KNOWN_TIERS else "standard"
