"""ADR-01：previewable / publishable / qa_ok 三分立。"""

from __future__ import annotations

import pytest

from app.forge.reliability.artifact_gate import ArtifactGate, derive_artifact_gate


def test_build_ok_without_qa_is_previewable_not_publishable() -> None:
    gate = derive_artifact_gate(build_ok=True, qa_ok=False)
    assert gate.generation_success is True
    assert gate.previewable is True
    assert gate.publishable is False
    assert gate.qa_ok is False


def test_qa_ok_implies_publishable() -> None:
    gate = derive_artifact_gate(build_ok=True, qa_ok=True)
    assert gate.previewable is True
    assert gate.publishable is True
    assert gate.qa_ok is True


def test_cannot_mark_publishable_without_qa() -> None:
    with pytest.raises(ValueError):
        ArtifactGate(
            generation_success=True,
            previewable=True,
            publishable=True,
            qa_ok=False,
        )


def test_build_failed_not_previewable() -> None:
    gate = derive_artifact_gate(build_ok=False, qa_ok=False)
    assert gate.generation_success is False
    assert gate.previewable is False
    assert gate.publishable is False
