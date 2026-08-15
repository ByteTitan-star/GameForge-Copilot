"""complete_stream 双协议 SSE 解析单测（不依赖真实 API，用 httpx MockTransport）。

这是流式改造最脆弱的点：Anthropic native（event:/data: 双行）与 OpenAI compat
（仅 data:、usage 单独成帧）两种格式各一套解析，必须各自覆盖 delta 提取与 usage 提取。
"""

from collections.abc import Iterable

import httpx
import pytest

from app.enums import LLMProvider
from app.llm import provider

ANTHROPIC_SSE = (
    "event: message_start\n"
    'data: {"type":"message_start","message":{"usage":{"input_tokens":12,"output_tokens":0}}}\n\n'
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"你好"}}\n\n'
    "event: content_block_delta\n"
    'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"世界"}}\n\n'
    "event: message_delta\n"
    'data: {"type":"message_delta","usage":{"output_tokens":7}}\n\n'
    "event: message_stop\n"
    'data: {"type":"message_stop"}\n\n'
)

OPENAI_SSE = (
    'data: {"choices":[{"delta":{"content":"你好"},"finish_reason":null}]}\n\n'
    'data: {"choices":[{"delta":{"content":"世界"},"finish_reason":null}]}\n\n'
    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    'data: {"usage":{"prompt_tokens":12,"completion_tokens":7}}\n\n'
    "data: [DONE]\n\n"
)

# 思考链帧（qwen 等会带 reasoning_content）必须被丢弃，content 才是正文
OPENAI_WITH_REASONING_SSE = (
    'data: {"choices":[{"delta":{"reasoning_content":"思考中"},"finish_reason":null}]}\n\n'
    'data: {"choices":[{"delta":{"content":"正文"},"finish_reason":null}]}\n\n'
    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    'data: {"usage":{"input_tokens":5,"output_tokens":3}}\n\n'
    "data: [DONE]\n\n"
)


def _sse_transport(sse_body: str) -> httpx.MockTransport:
    """把固定 SSE 字节串作为 POST 响应体的 MockTransport。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body.encode("utf-8"))

    return httpx.MockTransport(handler)


def _collect(chunks: Iterable[provider.StreamChunk]) -> tuple[str, provider.Usage | None]:
    text = "".join(c.delta for c in chunks)
    usage = next((c.usage for c in chunks if c.usage is not None), None)
    return text, usage


@pytest.mark.asyncio
async def test_anthropic_stream_parses_delta_and_usage(monkeypatch) -> None:
    # 走原生 /messages：provider=ANTHROPIC 且 base_url 为官方域名（或不传）
    monkeypatch.setattr(
        provider, "_build_llm_client", lambda url, timeout: httpx.AsyncClient(
            transport=_sse_transport(ANTHROPIC_SSE), timeout=timeout
        )
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.ANTHROPIC, "k", "claude-sonnet-5", "sys", "hi"
    ):
        chunks.append(chunk)
    text, usage = _collect(chunks)
    assert text == "你好世界"
    assert usage is not None and usage.input_tokens == 12 and usage.output_tokens == 7


@pytest.mark.asyncio
async def test_openai_stream_parses_delta_and_usage(monkeypatch) -> None:
    monkeypatch.setattr(
        provider, "_build_llm_client", lambda url, timeout: httpx.AsyncClient(
            transport=_sse_transport(OPENAI_SSE), timeout=timeout
        )
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.OPENAI_COMPAT, "k", "gpt-4o-mini", "sys", "hi", base_url="https://proxy.example.com/v1"
    ):
        chunks.append(chunk)
    text, usage = _collect(chunks)
    assert text == "你好世界"
    assert usage is not None and usage.input_tokens == 12 and usage.output_tokens == 7


@pytest.mark.asyncio
async def test_openai_stream_drops_reasoning_content(monkeypatch) -> None:
    monkeypatch.setattr(
        provider, "_build_llm_client", lambda url, timeout: httpx.AsyncClient(
            transport=_sse_transport(OPENAI_WITH_REASONING_SSE), timeout=timeout
        )
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.OPENAI_COMPAT, "k", "qwen3", "sys", "hi", base_url="https://dashscope.aliyuncs.com/v1"
    ):
        chunks.append(chunk)
    text, _ = _collect(chunks)
    assert text == "正文"  # 思考链 reasoning_content 被丢弃


@pytest.mark.asyncio
async def test_openai_stream_estimates_usage_when_missing(monkeypatch) -> None:
    """compat provider 不返回 usage 帧时，按字符数估算 output（~4 chars/token）。"""
    no_usage_sse = (
        'data: {"choices":[{"delta":{"content":"a"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{"content":"b"},"finish_reason":null}]}\n\n'
        'data: {"choices":[{"delta":{"content":"cdefghij"},"finish_reason":"stop"}]}\n\n'
        "data: [DONE]\n\n"
    )
    monkeypatch.setattr(
        provider, "_build_llm_client", lambda url, timeout: httpx.AsyncClient(
            transport=_sse_transport(no_usage_sse), timeout=timeout
        )
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.OPENAI_COMPAT, "k", "m", "sys", "hi", base_url="https://x.example.com/v1"
    ):
        chunks.append(chunk)
    text, usage = _collect(chunks)
    assert text == "abcdefghij"  # 10 字符
    assert usage is not None and usage.output_tokens == 2  # max(1, 10//4) = 2
