"""ADR Accept：机器证据核验。"""

from __future__ import annotations

from pathlib import Path

from app.forge.adr_evidence import collect_adr_evidence, evidence_all_machine_checks_ok


def test_adr_machine_evidence_all_pass() -> None:
    checks = collect_adr_evidence()
    assert checks, "expected machine-checkable ADR evidence"
    failed = [c for c in checks if not c.ok]
    assert failed == [], f"ADR evidence failed: {failed}"
    assert evidence_all_machine_checks_ok(checks) is True
    ids = {c.check_id for c in checks}
    assert "semantic_soft_hard_thresholds" in ids
    assert "embedding_default_bge_small" in ids


def test_adr_evidence_module_documents_invariants() -> None:
    import app.forge.adr_evidence as mod

    text = Path(mod.__file__).read_text(encoding="utf-8")
    assert "ADR-06" in text
    assert "semantic_soft_hard_thresholds" in text
    assert "daytona" in text
