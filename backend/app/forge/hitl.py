"""HITL phase vocabulary — single source of truth (ADR-10)."""

from __future__ import annotations

HITL_PHASES = frozenset({"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"})

_ALLOWED: dict[str, frozenset[str]] = {
    "plan_confirm": frozenset({"approve", "modify"}),
    "art_confirm": frozenset({"select_a", "select_b", "modify"}),
    "sandbox_failed": frozenset({"approve", "modify"}),
    "qa_failed": frozenset({"approve", "modify"}),
}


def is_hitl_phase(phase: str | None) -> bool:
    return phase in HITL_PHASES


def allowed_decisions_for(phase: str) -> frozenset[str]:
    return _ALLOWED[phase]
