"""Pure helpers for harvesting phase timing and QA telemetry from run events."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

_TERMINAL_EVENT_TYPES = frozenset({"done", "failed", "error"})


def _event_type(event: dict) -> str:
    raw = event.get("type", "")
    if isinstance(raw, StrEnum):
        return str(raw.value).lower()
    return str(getattr(raw, "value", raw)).lower()


def _parse_ts(ts: str) -> datetime:
    normalized = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def aggregate_phases(events: list[dict]) -> list[dict]:
    """Compute per-phase durations from phase_start and terminal events."""
    phase_starts: list[tuple[str, datetime]] = []
    terminal_ts: datetime | None = None

    for event in events:
        event_type = _event_type(event)
        ts = _parse_ts(event["ts"])
        if event_type == "phase_start":
            phase = event.get("payload", {}).get("phase")
            if phase:
                phase_starts.append((phase, ts))
        elif event_type in _TERMINAL_EVENT_TYPES and terminal_ts is None:
            terminal_ts = ts

    if not phase_starts:
        return []

    end_ts = terminal_ts or phase_starts[-1][1]
    phases: list[dict] = []
    for index, (name, start_ts) in enumerate(phase_starts):
        if index + 1 < len(phase_starts):
            next_ts = phase_starts[index + 1][1]
        else:
            next_ts = end_ts
        duration_s = (next_ts - start_ts).total_seconds()
        phases.append({"name": name, "duration_s": duration_s})
    return phases


def classify_qa_error(text: str) -> str:
    """Map QA/playtest error text to a coarse category."""
    lowered = text.lower()
    if "syntaxerror" in lowered or "syntax error" in lowered:
        return "syntax"
    if "typeerror" in lowered or "referenceerror" in lowered or "runtime" in lowered:
        return "runtime"
    if "canvas is blank" in lowered or "screenshot mismatch" in lowered or "visual" in lowered:
        return "visual"
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "infra" in lowered or "sandbox" in lowered:
        return "infra"
    return "unknown"


def derive_qa_metrics(
    *,
    attempts: int,
    first_playtest_ok: bool,
    final_playtest_ok: bool,
    error_categories: list[str],
) -> dict:
    """Summarize QA attempt counts and repair rounds."""
    first_pass = first_playtest_ok
    repair_rounds = 0 if first_pass else max(0, attempts - 1)
    return {
        "attempts": attempts,
        "first_pass": first_pass,
        "final_pass": final_playtest_ok,
        "repair_rounds": repair_rounds,
        "error_categories": error_categories,
    }


def is_empty_or_trivial_html(html: str) -> bool:
    """Return True when HTML is empty, shell-only, or lacks game bootstrapping."""
    stripped = html.strip()
    if not stripped:
        return True

    lowered = stripped.lower()
    has_canvas = "<canvas" in lowered
    has_script = "<script" in lowered
    if has_canvas and has_script:
        return False

    shell_only = "<html" in lowered and "<body" in lowered and not has_canvas and not has_script
    if shell_only:
        return True

    return len(stripped) < 80 and not has_canvas and not has_script
