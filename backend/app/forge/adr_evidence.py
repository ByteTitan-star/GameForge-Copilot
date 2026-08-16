"""ADR Accept 证据核验（Accepted 后仍校验运行时不变量）。"""

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
    """机器可核验项（与 Accepted 决策对齐）。"""
    checks: list[EvidenceCheck] = [
        EvidenceCheck(
            "ADR-02",
            "inferred_enabled_with_cap",
            settings.memory_preferences_inferred is True
            and settings.memory_preferences_max_active == 50,
            (
                f"inferred={settings.memory_preferences_inferred!r} "
                f"cap={settings.memory_preferences_max_active!r}"
            ),
        ),
        EvidenceCheck(
            "ADR-03",
            "e2b_enabled_by_default",
            settings.sandbox_e2b_enabled is True,
            f"sandbox_e2b_enabled={settings.sandbox_e2b_enabled!r}",
        ),
        EvidenceCheck(
            "ADR-03",
            "config_default_backend_is_e2b",
            _settings_field_default("sandbox_backend") == "e2b",
            "Settings.sandbox_backend field default must be e2b "
            "(runtime .env may still override for local)",
        ),
        EvidenceCheck(
            "ADR-03",
            "semantic_direct_hit_forbidden",
            semantic_direct_hit_allowed() is False,
            "semantic direct hit remains forbidden (shadow-only; no Pinecone)",
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


def _settings_field_default(name: str) -> object:
    from app.core.config import Settings

    return Settings.model_fields[name].default


def evidence_all_machine_checks_ok(checks: list[EvidenceCheck] | None = None) -> bool:
    rows = checks if checks is not None else collect_adr_evidence()
    return all(c.ok for c in rows)
