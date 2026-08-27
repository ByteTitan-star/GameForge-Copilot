"""Embedding client uses trust_env=False for local TEI (#147)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.llm import embeddings


@pytest.mark.asyncio
async def test_embed_texts_uses_trust_env_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_enabled", True)
    monkeypatch.setattr(settings, "embedding_apikey", "local")
    monkeypatch.setattr(settings, "embedding_base_url", "http://127.0.0.1:8080/v1")
    monkeypatch.setattr(settings, "embedding_model", "test-model")
    monkeypatch.setattr(settings, "embedding_timeout_s", 5)

    captured: dict[str, bool] = {}

    class _FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured["trust_env"] = bool(kwargs.get("trust_env"))

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: object, **_kwargs: object) -> object:
            class _Resp:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict[str, object]:
                    return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

            return _Resp()

    monkeypatch.setattr(embeddings.httpx, "AsyncClient", _FakeClient)

    out = await embeddings.embed_texts(["hello"])
    assert out == [[0.1, 0.2]]
    assert captured.get("trust_env") is False
