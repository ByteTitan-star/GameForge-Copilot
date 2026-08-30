"""Embedding client uses shared httpx client with trust_env=False (#147)."""

from __future__ import annotations

import pytest

from app.core import http_client
from app.core.config import settings
from app.llm import embeddings


@pytest.fixture(autouse=True)
async def _reset_http() -> None:
    await http_client.aclose_http_client()
    yield
    await http_client.aclose_http_client()


@pytest.mark.asyncio
async def test_embed_texts_uses_shared_client_trust_env_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_enabled", True)
    monkeypatch.setattr(settings, "embedding_apikey", "local")
    monkeypatch.setattr(settings, "embedding_base_url", "http://127.0.0.1:8080/v1")
    monkeypatch.setattr(settings, "embedding_model", "test-model")
    monkeypatch.setattr(settings, "embedding_timeout_s", 5)

    client = http_client.get_http_client()
    assert client.trust_env is False

    async def _fake_post(*_args: object, **_kwargs: object) -> object:
        class _Resp:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

        return _Resp()

    monkeypatch.setattr(client, "post", _fake_post)
    out = await embeddings.embed_texts(["hello"])
    assert out == [[0.1, 0.2]]
