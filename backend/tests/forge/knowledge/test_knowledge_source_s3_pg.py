"""S3 + DB knowledge source archive tests (#154)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.forge.knowledge.source_store import (
    archive_source,
    build_s3_content_ptr,
    read_source,
)
from app.models.knowledge_source import KnowledgeSource


@pytest.mark.asyncio
async def test_archive_s3_and_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_source_backend", "s3")
    monkeypatch.setattr(settings, "s3_bucket", "gf-test")
    monkeypatch.setattr(settings, "s3_ak", "ak")
    monkeypatch.setattr(settings, "s3_sk", "sk")
    monkeypatch.setattr(settings, "s3_endpoint", "http://127.0.0.1:9000")
    monkeypatch.setattr(settings, "s3_region", "us-east-1")
    monkeypatch.setattr(settings, "knowledge_s3_prefix", "knowledge-sources")

    store: dict[tuple[str, str], bytes] = {}

    class _Body:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def read(self) -> bytes:
            return self._data

    class _FakeS3:
        def put_object(self, *, Bucket: str, Key: str, Body: bytes, **_kw: object) -> None:
            store[(Bucket, Key)] = Body if isinstance(Body, bytes) else bytes(Body)

        def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
            return {"Body": _Body(store[(Bucket, Key)])}

    monkeypatch.setattr(
        "app.forge.knowledge.source_store._s3_client",
        lambda: _FakeS3(),
    )

    ptr = await archive_source(
        "## S3\n\n对象存储原文",
        source_id="src",
        document_id="doc",
        title="t",
    )
    assert ptr.startswith("s3://gf-test/knowledge-sources/")
    text = await read_source(ptr)
    assert "对象存储原文" in text


@pytest.mark.asyncio
async def test_archive_persists_db_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_session,
) -> None:
    monkeypatch.setattr(settings, "knowledge_source_backend", "local")
    monkeypatch.setattr(settings, "knowledge_source_root", str(tmp_path / "ks"))

    ptr = await archive_source(
        "## DB\n\n元数据行",
        source_id="src_db",
        document_id="doc_db",
        title="db-title",
        session=db_session,
    )
    assert ptr.startswith("local://")
    rows = (
        await db_session.scalars(
            select(KnowledgeSource).where(KnowledgeSource.source_id == "src_db")
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].content_ptr == ptr
    assert rows[0].title == "db-title"
    assert rows[0].backend == "local"


def test_build_s3_ptr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "s3_bucket", "bkt")
    monkeypatch.setattr(settings, "knowledge_s3_prefix", "knowledge-sources")
    ptr = build_s3_content_ptr(source_id="s", document_id="d", content_hash="ab" * 32)
    assert ptr.startswith("s3://bkt/knowledge-sources/s/d/")
