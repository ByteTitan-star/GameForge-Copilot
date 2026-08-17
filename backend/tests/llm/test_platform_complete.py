"""平台旁路 LLM（偏好抽取 / 语义确认等）：observe + provider.complete，不计用户配额。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core import langfuse as lf
from app.enums import LLMProvider
from app.llm import provider as llm_provider
from app.llm.provider import LLMCompletion, Usage


@pytest.mark.asyncio
async def test_platform_complete_writes_generation(monkeypatch) -> None:
    import app.llm.platform_complete as pc

    async def _fake_complete(
        prov: Any,
        apikey: Any,
        model: Any,
        system: Any,
        user_msg: Any,
        base_url: Any = None,
        *,
        max_tokens: int | None = None,
    ) -> LLMCompletion:
        _ = (prov, apikey, model, system, user_msg, base_url, max_tokens)
        return LLMCompletion(content='{"ok":true}', usage=Usage(3, 5))

    class _FakeGen:
        def __init__(self) -> None:
            self.updated: dict[str, Any] = {}

        def update(self, **kw: Any) -> None:
            self.updated.update(kw)

    class _FakeClient:
        def __init__(self) -> None:
            self.gen = _FakeGen()
            self.last_name: str | None = None

        def start_as_current_observation(self, *, as_type: str, name: str, **_: Any):
            from contextlib import contextmanager

            self.last_name = name

            @contextmanager
            def _cm():
                yield self.gen

            return _cm()

    fake = _FakeClient()
    monkeypatch.setattr(lf, "_client", lambda: fake)
    monkeypatch.setattr(llm_provider, "complete", _fake_complete)

    content, usage = await pc.platform_complete(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "user",
        kind="preference_extract",
        base_url=None,
        max_tokens=512,
        metadata={"game_id": "g1"},
        tags=["forge", "memory"],
    )
    assert content == '{"ok":true}'
    assert usage == Usage(3, 5)
    assert fake.last_name == "llm:preference_extract"
    assert fake.gen.updated["output"] == '{"ok":true}'
    assert fake.gen.updated["usage_details"] == {"input": 3, "output": 5}


@pytest.mark.asyncio
async def test_platform_complete_marks_error(monkeypatch) -> None:
    import app.llm.platform_complete as pc

    async def _boom(*_: Any, **__: Any) -> tuple[str, Usage]:
        raise RuntimeError("boom")

    class _FakeGen:
        def __init__(self) -> None:
            self.updated: dict[str, Any] = {}

        def update(self, **kw: Any) -> None:
            self.updated.update(kw)

    class _FakeClient:
        def __init__(self) -> None:
            self.gen = _FakeGen()

        def start_as_current_observation(self, *, as_type: str, name: str, **_: Any):
            from contextlib import contextmanager

            @contextmanager
            def _cm():
                yield self.gen

            return _cm()

    fake = _FakeClient()
    monkeypatch.setattr(lf, "_client", lambda: fake)
    monkeypatch.setattr(llm_provider, "complete", _boom)

    with pytest.raises(RuntimeError):
        await pc.platform_complete(
            LLMProvider.OPENAI_COMPAT,
            "k",
            "m",
            "s",
            "u",
            kind="semantic_confirm",
        )
    assert fake.gen.updated.get("level") == "ERROR"
