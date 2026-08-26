"""Knowledge probe tests."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.knowledge.probe import probe_knowledge_stack


@pytest.mark.asyncio
async def test_probe_fails_when_knowledge_host_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "")
    monkeypatch.setattr(settings, "embedding_apikey", "key")
    monkeypatch.setattr(settings, "embedding_base_url", "http://localhost/v1")
    result = await probe_knowledge_stack()
    assert result.ok is False
    assert "knowledge pinecone not configured" in result.errors[0]
    assert result.hints


@pytest.mark.asyncio
async def test_probe_ok_with_mocked_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", True)
    monkeypatch.setattr(settings, "pinecone_api_key", "test-key")
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "example.pinecone.io")
    monkeypatch.setattr(settings, "pinecone_knowledge_namespace", "global")
    monkeypatch.setattr(settings, "embedding_enabled", True)
    monkeypatch.setattr(settings, "embedding_apikey", "key")
    monkeypatch.setattr(settings, "embedding_base_url", "http://localhost/v1")
    monkeypatch.setattr(settings, "embedding_model", "test-model")

    async def _fake_embed(_text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def _fake_post(path: str, body: dict) -> dict:
        if path == "query":
            filt = body.get("filter") if isinstance(body.get("filter"), dict) else None
            if filt and filt.get("chunk_id") == "__gameforge_connectivity_probe__":
                return {
                    "matches": [
                        {"id": "__gameforge_connectivity_probe__", "score": 1.0, "metadata": {}}
                    ]
                }
            return {"matches": [{"id": "a", "score": 0.9, "metadata": {}}]}
        if path.endswith("upsert"):
            return {"upsertedCount": 1}
        return {}

    monkeypatch.setattr("app.forge.knowledge.probe.embed_one", _fake_embed)
    monkeypatch.setattr("app.forge.knowledge.probe._strict_pinecone_post", _fake_post)

    result = await probe_knowledge_stack(write_probe=True)
    assert result.ok is True
    assert result.embedding_ok is True
    assert result.vector_dim == 3
    assert result.write_probe_ok is True
