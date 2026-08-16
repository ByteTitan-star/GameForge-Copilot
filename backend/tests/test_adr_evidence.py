"""ADR Accept：机器证据核验（不自动 Accept）。"""

from __future__ import annotations

from app.forge.adr_evidence import collect_adr_evidence, evidence_all_machine_checks_ok


def test_adr_machine_evidence_all_pass() -> None:
    checks = collect_adr_evidence()
    assert checks, "expected machine-checkable ADR evidence"
    failed = [c for c in checks if not c.ok]
    assert failed == [], f"ADR evidence failed: {failed}"
    assert evidence_all_machine_checks_ok(checks) is True


def test_adr_evidence_never_claims_accepted_in_module_doc() -> None:
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath(
        "app", "forge", "adr_evidence.py"
    ).read_text(encoding="utf-8")
    assert "永不改 ADR Status" in text or "never" in text.lower()
