"""Pinecone store factory：默认路径不得返回裸 object 哨兵。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import (
    HttpPineconeStore,
    get_pinecone_store,
    pinecone_configured,
    reset_pinecone_store_override,
)


@pytest.fixture(autouse=True)
def _reset_override() -> None:
    reset_pinecone_store_override()
    yield
    reset_pinecone_store_override()


def test_get_pinecone_store_default_without_config_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", True)
    monkeypatch.setattr(settings, "pinecone_api_key", "")
    monkeypatch.setattr(settings, "pinecone_host", "")

    assert pinecone_configured() is False
    assert get_pinecone_store() is None


def test_get_pinecone_store_default_with_config_returns_http_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", True)
    monkeypatch.setattr(settings, "pinecone_api_key", "test-key")
    monkeypatch.setattr(settings, "pinecone_host", "example.pinecone.io")
    monkeypatch.setattr(settings, "pinecone_namespace", "default")

    store = get_pinecone_store()
    assert isinstance(store, HttpPineconeStore)
