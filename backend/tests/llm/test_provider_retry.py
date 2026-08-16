"""LLM 传输层重试：瞬时网络错误 / 429 / 502-504 有限退避，与业务预算正交。"""

from __future__ import annotations

import httpx
import pytest
from app.core.errors import AppError
from app.enums import LLMProvider
from app.llm import provider


def _json_ok() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


@pytest.mark.asyncio
async def test_complete_retries_on_429_then_succeeds(monkeypatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, text="rate limited")
        return _json_ok()

    monkeypatch.setattr(provider.settings, "llm_http_max_retries", 3)
    monkeypatch.setattr(provider.settings, "llm_http_retry_base_delay_s", 0.01)
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=timeout
        ),
    )
    content, usage = await provider.complete(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "hi",
        base_url="https://x.example.com/v1",
    )
    assert content == "ok"
    assert usage.input_tokens == 1
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_complete_retries_transport_error(monkeypatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return _json_ok()

    monkeypatch.setattr(provider.settings, "llm_http_max_retries", 2)
    monkeypatch.setattr(provider.settings, "llm_http_retry_base_delay_s", 0.01)
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=timeout
        ),
    )
    content, _ = await provider.complete(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "hi",
        base_url="https://x.example.com/v1",
    )
    assert content == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_complete_does_not_retry_400(monkeypatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        calls["n"] += 1
        return httpx.Response(400, text="bad request")

    monkeypatch.setattr(provider.settings, "llm_http_max_retries", 3)
    monkeypatch.setattr(provider.settings, "llm_http_retry_base_delay_s", 0.01)
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=timeout
        ),
    )
    with pytest.raises(AppError, match="HTTP 400"):
        await provider.complete(
            LLMProvider.OPENAI_COMPAT,
            "k",
            "m",
            "sys",
            "hi",
            base_url="https://x.example.com/v1",
        )
    assert calls["n"] == 1
