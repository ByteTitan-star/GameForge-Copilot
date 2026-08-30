"""Knowledge readiness gate script tests."""

from __future__ import annotations

import pytest

from app.core.config import settings
from scripts.knowledge_readiness_gate import collect_gate_items, main


def test_collect_gate_items_reports_default_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_rag_enabled", False)
    items = {i.name: i for i in collect_gate_items()}
    assert items["default_flag_off"].ok is True


def test_main_fails_on_hard_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", False)
    monkeypatch.setattr(settings, "pinecone_api_key", "")
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "")
    monkeypatch.setattr(settings, "embedding_enabled", False)
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 0)
    monkeypatch.setattr(settings, "knowledge_embedding_expected_model", "")
    assert main() == 1
