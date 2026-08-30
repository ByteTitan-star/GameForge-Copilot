"""Production chunking ingest wiring (#146)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge.ingest import (
    ingest_corpus,
    specs_from_markdown,
    upsert_knowledge_spec,
)
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_knowledge_pinecone_store_override()
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)
    monkeypatch.setattr(settings, "knowledge_metadata_validation_enabled", True)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)
    yield
    reset_knowledge_pinecone_store_override()


@pytest.mark.asyncio
async def test_markdown_ingest_writes_chunk_metadata() -> None:
    md = """## 机制

随机成长应绑定稀有度曲线。

## 案例

经典塔防强调路线与射程覆盖。
"""
    specs = specs_from_markdown(
        md,
        document_id="doc_td",
        domain="design",
        category="gameplay_mechanic",
        title="塔防笔记",
        source_id="src_md",
        content_ptr="/tmp/td.md",
    )
    assert len(specs) >= 2
    assert specs[0].document_id == "doc_td"
    assert specs[0].chunk_policy == "design_principle"
    assert specs[0].chunk_index == 0
    assert specs[0].chunk_total == len(specs)
    assert specs[0].content_hash

    result = await ingest_corpus(specs)
    assert result.upserted == len(specs)
    assert result.errors == ()

    store = __import__(
        "app.forge.knowledge.pinecone_store", fromlist=["get_knowledge_writer"]
    ).get_knowledge_writer()
    assert store is not None
    rows = store._rows  # type: ignore[attr-defined]
    meta = next(iter(rows.values()))[1]
    assert meta["document_id"] == "doc_td"
    assert "chunk_index" in meta
    assert meta["chunk_policy"] == "design_principle"
    assert len(meta["text"]) <= 2000


@pytest.mark.asyncio
async def test_ingest_markdown_file_archives_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.forge.knowledge.ingest import ingest_markdown_file

    monkeypatch.setattr(settings, "knowledge_source_root", str(tmp_path / "ks"))
    md = tmp_path / "note.md"
    md.write_text("## 原则\n\n短文即可归档。\n", encoding="utf-8")
    result = await ingest_markdown_file(
        md,
        document_id="doc_md",
        domain="design",
        category="design_principle",
        title="note",
        source_id="src_md",
    )
    assert result.upserted >= 1
    store = __import__(
        "app.forge.knowledge.pinecone_store", fromlist=["get_knowledge_writer"]
    ).get_knowledge_writer()
    assert store is not None
    meta = next(iter(store._rows.values()))[1]  # type: ignore[attr-defined]
    ptr = str(meta["content_ptr"])
    assert ptr.startswith("local://knowledge-sources/")
    from app.forge.knowledge.source_store import read_source_text

    assert "短文即可归档" in read_source_text(ptr)


@pytest.mark.asyncio
async def test_reingest_same_content_hash_is_idempotent() -> None:
    specs = specs_from_markdown(
        "## 原则\n\n短文本即可。",
        document_id="doc_x",
        domain="design",
        category="design_principle",
        title="t",
        source_id="src",
    )
    first = await ingest_corpus(specs)
    second = await ingest_corpus(specs)
    assert first.upserted == len(specs)
    assert second.upserted == 0
    assert second.skipped == len(specs)


@pytest.mark.asyncio
async def test_oversized_json_chunk_rejected() -> None:
    from app.forge.knowledge.ingest import KnowledgeChunkSpec

    huge = "机" * 600
    spec = KnowledgeChunkSpec(
        chunk_id="too_big",
        text=huge,
        domain="design",
        category="design_principle",
        title="t",
        source_id="s",
        chunk_policy="design_principle",
    )
    ok = await upsert_knowledge_spec(spec)
    assert ok is False
