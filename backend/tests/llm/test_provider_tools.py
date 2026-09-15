"""原生工具调用（ADR-18）单测：请求构造 / 双协议解析 / 流式 tool_calls 聚合 / 能力表。

不依赖真实 API：_build_body 纯构造直接断言；SSE 解析用 httpx MockTransport。
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import httpx
import pytest

from app.enums import LLMProvider
from app.llm import provider

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "ask",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]

MESSAGES = [
    {"role": "system", "content": "SYS"},
    {"role": "user", "content": "REQ"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "ask_1",
                "type": "function",
                "function": {"name": "ask_user", "arguments": '{"question":"Q?"}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "ask_1", "content": "答"},
]

# --------------------------------------------------------------------------- #
# _build_body：tools / messages 按协议构造
# --------------------------------------------------------------------------- #


def test_openai_body_carries_tools_and_messages() -> None:
    body = provider._build_body(
        LLMProvider.OPENAI_COMPAT,
        "m",
        "",
        "",
        "https://p.example.com/v1",
        max_tokens=10,
        stream=False,
        messages=MESSAGES,
        tools=TOOLS,
        tool_choice="auto",
    )
    assert body["tools"] == TOOLS
    assert body["tool_choice"] == "auto"
    assert body["messages"] == MESSAGES  # OpenAI 规范形态直传


def test_body_without_tools_has_no_new_fields() -> None:
    """未传 tools 的调用与既有请求体完全一致（compat 端点不感知新字段）。"""
    body = provider._build_body(
        LLMProvider.OPENAI_COMPAT,
        "m",
        "sys",
        "hi",
        "https://p.example.com/v1",
        max_tokens=10,
        stream=False,
    )
    assert "tools" not in body and "tool_choice" not in body
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_anthropic_body_converts_tools_and_messages() -> None:
    body = provider._build_body(
        LLMProvider.ANTHROPIC,
        "claude-sonnet-5",
        "",
        "",
        None,
        max_tokens=10,
        stream=False,
        messages=MESSAGES,
        tools=TOOLS,
        tool_choice="auto",
    )
    # tools → name/description/input_schema
    assert body["tools"][0]["name"] == "ask_user"
    assert body["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert body["tool_choice"] == {"type": "auto"}
    # messages：assistant tool_calls → tool_use block；role:tool → user tool_result block
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant", "user"]
    assistant_blocks = body["messages"][1]["content"]
    assert assistant_blocks[0]["type"] == "tool_use"
    assert assistant_blocks[0]["id"] == "ask_1"
    assert assistant_blocks[0]["input"] == {"question": "Q?"}
    tool_result = body["messages"][2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "ask_1"
    assert tool_result["content"] == "答"


def test_anthropic_messages_merge_system() -> None:
    body = provider._build_body(
        LLMProvider.ANTHROPIC,
        "claude-sonnet-5",
        "BASE_SYS",
        "",
        None,
        max_tokens=10,
        stream=False,
        messages=[{"role": "system", "content": "EXTRA"}, {"role": "user", "content": "hi"}],
    )
    assert "BASE_SYS" in body["system"] and "EXTRA" in body["system"]


# --------------------------------------------------------------------------- #
# 非流式解析：tool_calls（MockTransport 直接返回 JSON）
# --------------------------------------------------------------------------- #


def _json_transport(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_openai_complete_parses_tool_calls(monkeypatch) -> None:
    payload = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "ask_user",
                                "arguments": '{"question":"Q?"}',
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
    }
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=_json_transport(payload), timeout=timeout
        ),
    )
    result = await provider.complete(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "hi",
        base_url="https://p.example.com/v1",
    )
    assert result.tool_calls is not None
    assert result.tool_calls[0]["function"]["name"] == "ask_user"
    assert result.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_anthropic_complete_parses_tool_use(monkeypatch) -> None:
    payload = {
        "content": [
            {"type": "text", "text": ""},
            {"type": "tool_use", "id": "tu_1", "name": "ask_user", "input": {"question": "Q?"}},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 3, "output_tokens": 2},
    }
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=_json_transport(payload), timeout=timeout
        ),
    )
    result = await provider.complete(LLMProvider.ANTHROPIC, "k", "claude-sonnet-5", "sys", "hi")
    assert result.tool_calls is not None
    call = result.tool_calls[0]
    assert call["id"] == "tu_1"
    assert call["function"]["name"] == "ask_user"
    assert json.loads(call["function"]["arguments"]) == {"question": "Q?"}
    assert result.finish_reason == "tool_use"


# --------------------------------------------------------------------------- #
# 流式解析：tool_calls 增量聚合（两协议各自一套；SSE 行用 json.dumps 构造避免转义错）
# --------------------------------------------------------------------------- #


def _openai_frame(delta: dict, finish_reason: str | None = None) -> str:
    return "data: " + json.dumps(
        {"choices": [{"delta": delta, "finish_reason": finish_reason}]}
    ) + "\n\n"


OPENAI_TOOL_SSE = (
    _openai_frame(
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "ask_user", "arguments": ""},
                }
            ]
        }
    )
    + _openai_frame(
        {"tool_calls": [{"index": 0, "function": {"arguments": '{"quest'}}]}
    )
    + _openai_frame(
        {"tool_calls": [{"index": 0, "function": {"arguments": 'ion": "Q?"}'}}]}
    )
    + _openai_frame({}, finish_reason="tool_calls")
    + 'data: {"usage":{"prompt_tokens":5,"completion_tokens":3}}\n\n'
    + "data: [DONE]\n\n"
)


def _anthropic_event(etype: str, data: dict) -> str:
    return f"event: {etype}\ndata: {json.dumps({'type': etype, **data})}\n\n"


ANTHROPIC_TOOL_SSE = (
    _anthropic_event(
        "message_start", {"message": {"usage": {"input_tokens": 5, "output_tokens": 0}}}
    )
    + _anthropic_event(
        "content_block_start",
        {"index": 0, "content_block": {"type": "tool_use", "id": "tu_1", "name": "ask_user"}},
    )
    + _anthropic_event(
        "content_block_delta",
        {"index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"quest'}},
    )
    + _anthropic_event(
        "content_block_delta",
        {"index": 0, "delta": {"type": "input_json_delta", "partial_json": 'ion": "Q?"}'}},
    )
    + _anthropic_event("message_delta", {"usage": {"output_tokens": 3}})
    + _anthropic_event("message_stop", {})
)


def _sse_transport(sse_body: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body.encode("utf-8"))

    return httpx.MockTransport(handler)


def _final(chunks: Iterable[provider.StreamChunk]) -> provider.StreamChunk:
    return next(c for c in chunks if c.tool_calls or c.usage is not None)


@pytest.mark.asyncio
async def test_openai_stream_accumulates_tool_call_fragments(monkeypatch) -> None:
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=_sse_transport(OPENAI_TOOL_SSE), timeout=timeout
        ),
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "hi",
        base_url="https://p.example.com/v1",
    ):
        chunks.append(chunk)
    final = _final(chunks)
    assert final.tool_calls is not None
    call = final.tool_calls[0]
    assert call["id"] == "c1"
    assert call["function"]["name"] == "ask_user"
    assert json.loads(call["function"]["arguments"]) == {"question": "Q?"}
    assert final.finish_reason == "tool_calls"
    assert final.usage is not None and final.usage.input_tokens == 5


@pytest.mark.asyncio
async def test_anthropic_stream_accumulates_tool_use(monkeypatch) -> None:
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=_sse_transport(ANTHROPIC_TOOL_SSE), timeout=timeout
        ),
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.ANTHROPIC, "k", "claude-sonnet-5", "sys", "hi"
    ):
        chunks.append(chunk)
    final = _final(chunks)
    assert final.tool_calls is not None
    call = final.tool_calls[0]
    assert call["id"] == "tu_1"
    assert call["function"]["name"] == "ask_user"
    assert json.loads(call["function"]["arguments"]) == {"question": "Q?"}
    assert final.usage is not None and final.usage.output_tokens == 3


# --------------------------------------------------------------------------- #
# 能力表：BYOK 降级
# --------------------------------------------------------------------------- #


def test_tools_supported_default_and_blocklist(monkeypatch) -> None:
    from app.core.config import settings

    assert provider.tools_supported(LLMProvider.OPENAI, "gpt-4o")
    assert provider.tools_supported(LLMProvider.OPENAI_COMPAT, "deepseek-chat")
    assert provider.tools_supported(LLMProvider.ANTHROPIC, "claude-sonnet-5")

    monkeypatch.setattr(settings, "llm_tools_blocklist", "some-old-model,other")
    assert not provider.tools_supported(LLMProvider.OPENAI_COMPAT, "some-old-model-v1")
    assert provider.tools_supported(LLMProvider.OPENAI_COMPAT, "fine-model")


# --------------------------------------------------------------------------- #
# 运行时降级：绑定 tools 收到 400 → 自动去 tools 重试一次（不抛错）
# --------------------------------------------------------------------------- #

_OK_OPENAI_PAYLOAD = {
    "choices": [{"finish_reason": "stop", "message": {"content": "正文"}}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
}

_OK_OPENAI_SSE = (
    'data: {"choices":[{"delta":{"content":"正文"},"finish_reason":null}]}\n\n'
    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    'data: {"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\n'
    "data: [DONE]\n\n"
)


def _reject_tools_transport(ok_payload, *, sse: bool) -> httpx.MockTransport:
    """请求体带 tools → 400；不带 → 200 正常响应。"""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        if "tools" in body:
            return httpx.Response(400, json={"error": {"message": "tools not supported"}})
        if sse:
            return httpx.Response(
                200,
                content=_OK_OPENAI_SSE.encode("utf-8"),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(200, json=ok_payload)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_complete_degrades_tools_on_400(monkeypatch) -> None:
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=_reject_tools_transport(_OK_OPENAI_PAYLOAD, sse=False), timeout=timeout
        ),
    )
    result = await provider.complete(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "hi",
        base_url="https://p.example.com/v1",
        tools=TOOLS,
    )
    assert result.content == "正文"  # 降级后正常返回，不把 400 抛给用户
    assert result.tool_calls is None


@pytest.mark.asyncio
async def test_complete_stream_degrades_tools_on_400(monkeypatch) -> None:
    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=_reject_tools_transport(None, sse=True), timeout=timeout
        ),
    )
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider.OPENAI_COMPAT,
        "k",
        "m",
        "sys",
        "hi",
        base_url="https://p.example.com/v1",
        tools=TOOLS,
    ):
        chunks.append(chunk)
    assert "".join(c.delta for c in chunks) == "正文"


@pytest.mark.asyncio
async def test_complete_without_tools_still_raises_400(monkeypatch) -> None:
    """未绑定 tools 的 400 与能力无关，必须照常抛错（不误降级）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    monkeypatch.setattr(
        provider,
        "_build_llm_client",
        lambda url, timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), timeout=timeout
        ),
    )
    from app.core.errors import AppError

    with pytest.raises(AppError):
        await provider.complete(
            LLMProvider.OPENAI_COMPAT,
            "k",
            "m",
            "sys",
            "hi",
            base_url="https://p.example.com/v1",
        )
