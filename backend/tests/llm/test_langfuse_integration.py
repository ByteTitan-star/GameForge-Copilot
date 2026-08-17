"""langfuse 集成：未配置 key 时全程空操作；配置 client 时 _invoke_llm 正确写 output/usage。

测试不触达 Langfuse 云：未配置 key 走 no-op 分支；启用分支注入 fake client。
"""

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

from app.core import langfuse as lf
from app.core.config import settings
from app.enums import LLMProvider
from app.llm import client as llm_client
from app.llm import provider as llm_provider
from app.llm.provider import LLMCompletion, Usage


def test_client_none_when_unconfigured() -> None:
    """conftest 已清空 key，_client 必须返回 None，不导入/触达 SDK。"""
    assert settings.langfuse_public_key == ""
    assert lf._client() is None


def test_observe_generation_noop_when_unconfigured() -> None:
    """无 key 时 observe_generation yield None，不抛、不注册。"""
    with lf.observe_generation(model="m", provider="anthropic", system="s", user_msg="u") as gen:
        assert gen is None


async def test_invoke_llm_transparent_when_unconfigured(monkeypatch) -> None:
    """langfuse 禁用时 _invoke_llm 仅透传 provider.complete 的 content 与 usage。"""

    async def _fake_complete(
        prov: Any,
        apikey: Any,
        model: Any,
        system: Any,
        user_msg: Any,
        *,
        base_url: Any,
        max_tokens: Any = None,
    ) -> LLMCompletion:
        _ = (prov, apikey, model, system, user_msg, base_url, max_tokens)
        return LLMCompletion(content="hello", usage=Usage(7, 11))

    monkeypatch.setattr(llm_provider, "complete", _fake_complete)
    result = await llm_client._invoke_llm(
        LLMProvider.ANTHROPIC, "k", "model-x", "sys", "hi", None, {"user_id": "u"}
    )
    assert result.content == "hello"
    assert result.usage == Usage(7, 11)


class _FakeGen:
    def __init__(self) -> None:
        self.updated: dict[str, Any] = {}

    def update(self, **kw: Any) -> None:
        self.updated.update(kw)


class _FakeClient:
    def __init__(self) -> None:
        self.gen = _FakeGen()
        self.last_name: str | None = None
        self.last_kwargs: dict[str, Any] = {}

    @contextmanager
    def start_as_current_observation(
        self, *, as_type: str, name: str, **kwargs: Any
    ) -> Iterator[_FakeGen]:
        self.last_name = name
        self.last_kwargs = {"as_type": as_type, **kwargs}
        yield self.gen


def test_observe_generation_name_uses_kind(monkeypatch) -> None:
    """generation name 为 llm:{kind}，metadata 含 kind。"""
    fake = _FakeClient()
    monkeypatch.setattr(lf, "_client", lambda: fake)
    with lf.observe_generation(
        model="m",
        provider="openai_compat",
        system="s",
        user_msg="u",
        kind="preference_extract",
        metadata={"user_id": "u1"},
    ) as gen:
        assert gen is fake.gen
    assert fake.last_name == "llm:preference_extract"
    meta = fake.last_kwargs.get("metadata") or {}
    assert meta.get("kind") == "preference_extract"
    assert meta.get("provider") == "openai_compat"
    assert meta.get("user_id") == "u1"


def test_propagate_trace_attrs_noop_when_unconfigured() -> None:
    """无 key 时 propagate_trace_attrs 空操作，不抛。"""
    with lf.propagate_trace_attrs(user_id="u", session_id="g", tags=["forge"]):
        pass


async def test_invoke_llm_writes_generation_when_enabled(monkeypatch) -> None:
    """注入 fake client：_invoke_llm 成功后写 output 与 usage_details（int 字典）。"""

    async def _fake_complete(
        prov: Any,
        apikey: Any,
        model: Any,
        system: Any,
        user_msg: Any,
        *,
        base_url: Any,
        max_tokens: Any = None,
    ) -> LLMCompletion:
        _ = (prov, apikey, model, system, user_msg, base_url, max_tokens)
        return LLMCompletion(content="<html></html>", usage=Usage(13, 9))

    monkeypatch.setattr(llm_provider, "complete", _fake_complete)
    fake = _FakeClient()
    monkeypatch.setattr(lf, "_client", lambda: fake)

    result = await llm_client._invoke_llm(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "gpt-x",
        "sys",
        "hi",
        "https://x/v1",
        {},
        kind="plan",
    )
    assert result.content == "<html></html>"
    assert result.usage == Usage(13, 9)
    # 关键：usage_details 必须是 int 字典（v4 SDK 入参），output 为 LLM 文本
    assert fake.gen.updated["output"] == "<html></html>"
    assert fake.gen.updated["usage_details"] == {"input": 13, "output": 9}
    assert fake.last_name == "llm:plan"


async def test_invoke_llm_marks_error_on_failure(monkeypatch) -> None:
    """provider.complete 抛错时 generation 标 level=ERROR 后 re-raise。"""

    async def _boom(*_: Any, **__: Any) -> tuple[str, Usage]:
        raise RuntimeError("boom")

    monkeypatch.setattr(llm_provider, "complete", _boom)
    fake = _FakeClient()
    monkeypatch.setattr(lf, "_client", lambda: fake)

    with suppress(RuntimeError):
        await llm_client._invoke_llm(LLMProvider.ANTHROPIC, "k", "m", "s", "u", None, {})
    assert fake.gen.updated.get("level") == "ERROR"
