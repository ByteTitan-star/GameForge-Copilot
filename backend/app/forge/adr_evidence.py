"""ADR Accept 证据自动核验：只报告 pass/fail，永不改 ADR Status 为 Accepted。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.forge.cache.semantic import semantic_direct_hit_allowed
from app.models.forge_message import ForgeMessage


@dataclass(frozen=True)
class EvidenceCheck:
    adr: str
    check_id: str
    ok: bool
    detail: str


def collect_adr_evidence() -> list[EvidenceCheck]:
    """机器可核验项；文案/合规签字仍须人工。"""
    checks: list[EvidenceCheck] = [
        EvidenceCheck(
            "ADR-02",
            "inferred_flag_default_off",
            settings.memory_preferences_inferred is False,
            f"memory_preferences_inferred={settings.memory_preferences_inferred!r}",
        ),
        EvidenceCheck(
            "ADR-03",
            "e2b_disabled_by_default",
            settings.sandbox_e2b_enabled is False,
            f"sandbox_e2b_enabled={settings.sandbox_e2b_enabled!r}",
        ),
        EvidenceCheck(
            "ADR-03",
            "default_backend_not_e2b",
            (settings.sandbox_backend or "").lower() != "e2b",
            f"sandbox_backend={settings.sandbox_backend!r}",
        ),
        EvidenceCheck(
            "ADR-03",
            "semantic_direct_hit_forbidden",
            semantic_direct_hit_allowed() is False,
            "semantic_direct_hit_allowed() must stay False until calibration",
        ),
        EvidenceCheck(
            "ADR-04",
            "forge_messages_tablename",
            ForgeMessage.__tablename__ == "forge_messages",
            f"tablename={ForgeMessage.__tablename__!r}",
        ),
        EvidenceCheck(
            "ADR-04",
            "accept_checklist_present",
            _accept_checklist_path().is_file(),
            "docs/adr/ACCEPT-CHECKLIST.md",
        ),
    ]
    return checks


def _accept_checklist_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "adr" / "ACCEPT-CHECKLIST.md"


def evidence_all_machine_checks_ok(checks: list[EvidenceCheck] | None = None) -> bool:
    rows = checks if checks is not None else collect_adr_evidence()
    return all(c.ok for c in rows)
