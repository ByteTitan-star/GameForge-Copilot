"""Knowledge RAG circuit breaker (#147 P0)."""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge import circuit as knowledge_circuit
from app.forge.knowledge.circuit import (
    failure_count,
    knowledge_circuit_is_open,
    record_knowledge_failure,
    record_knowledge_success,
    reset_knowledge_circuit,
)
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)
from app.forge.knowledge.retriever import retrieve_knowledge_for_node


@pytest.fixture(autouse=True)
def _reset_circuit_and_store(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_knowledge_circuit()
    reset_knowledge_pinecone_store_override()
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_circuit_enabled", True)
    monkeypatch.setattr(settings, "knowledge_circuit_failure_threshold", 3)
    monkeypatch.setattr(settings, "knowledge_circuit_open_s", 60.0)
    yield
    reset_knowledge_circuit()
    reset_knowledge_pinecone_store_override()


def test_circuit_opens_after_threshold() -> None:
    assert knowledge_circuit_is_open() is False
    record_knowledge_failure()
    record_knowledge_failure()
    assert knowledge_circuit_is_open() is False
    record_knowledge_failure()
    assert knowledge_circuit_is_open() is True


def test_circuit_success_resets_failures() -> None:
    record_knowledge_failure()
    record_knowledge_failure()
    record_knowledge_success()
    record_knowledge_failure()
    assert knowledge_circuit_is_open() is False


@pytest.mark.asyncio
async def test_retrieve_short_circuits_when_open() -> None:
    calls = {"n": 0}

    class BoomStore(InMemoryPineconeStore):
        async def query(self, *args: object, **kwargs: object) -> list[object]:
            calls["n"] += 1
            raise RuntimeError("should not be called")

    set_knowledge_pinecone_store_override(BoomStore())
    record_knowledge_failure()
    record_knowledge_failure()
    record_knowledge_failure()
    assert knowledge_circuit_is_open() is True

    out = await retrieve_knowledge_for_node(
        node="plan",
        current_input="塔防游戏设计要点",
        design_doc={"title": "塔防"},
    )
    assert out == []
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_retrieve_records_failure_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _slow(*_a: object, **_k: object) -> tuple[list[object], str, int, float]:
        await asyncio.sleep(1.0)
        return [], "ok", 0, 0.0

    monkeypatch.setattr(settings, "knowledge_retrieve_timeout_s", 0.05)
    monkeypatch.setattr(
        "app.forge.knowledge.retriever._retrieve_knowledge_inner",
        _slow,
    )
    reset_knowledge_circuit()
    out = await retrieve_knowledge_for_node(
        node="plan",
        current_input="塔防",
        design_doc=None,
    )
    assert out == []
    assert failure_count() == 1
    assert knowledge_circuit.failure_count() == 1
