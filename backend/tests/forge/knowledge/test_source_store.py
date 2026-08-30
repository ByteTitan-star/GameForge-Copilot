"""Local knowledge source archive tests (#146 follow-up)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.forge.knowledge.source_store import (
    archive_source_text,
    build_content_ptr,
    read_source_text,
    resolve_content_ptr,
)


@pytest.fixture()
def archive_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "ks"
    monkeypatch.setattr(settings, "knowledge_source_root", str(root))
    return root


def test_archive_and_read_roundtrip(archive_root: Path) -> None:
    ptr = archive_source_text(
        "## Hello\n\n世界",
        source_id="src_a",
        document_id="doc_1",
    )
    assert ptr.startswith("local://knowledge-sources/")
    path = resolve_content_ptr(ptr)
    assert path.is_file()
    assert "世界" in read_source_text(ptr)
    # idempotent
    ptr2 = archive_source_text(
        "## Hello\n\n世界",
        source_id="src_a",
        document_id="doc_1",
    )
    assert ptr2 == ptr


def test_build_content_ptr_stable() -> None:
    a = build_content_ptr(source_id="s", document_id="d", content_hash="a" * 64)
    b = build_content_ptr(source_id="s", document_id="d", content_hash="a" * 64)
    assert a == b


def test_reject_path_traversal(archive_root: Path) -> None:
    with pytest.raises(ValueError):
        resolve_content_ptr("local://knowledge-sources/../etc/passwd")
