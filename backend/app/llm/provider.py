"""LLM provider 抽象：连通性测试 + complete() 调用。

docs/05 §连通性测试：保存前发最小 completion，失败不让保存。
complete() 返回 (content, usage)，usage 取响应真实字段，不估算（docs/05）。
"""

import asyncio
import base64
import logging
import random
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import LLMProvider
from app.llm.thinking import thinking_disable_fields

log = logging.getLogger(__name__)

# 传输层可重试状态：限流与网关瞬时故障（与业务自修复预算正交）
_RETRYABLE_HTTP_STATUS = frozenset({429, 502, 503, 504})

_DEFAULT_API_BASE = {
    LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1",
    LLMProvider.OPENAI: "https://api.openai.com/v1",
}

# 官方 API 域名；自定义 base_url 走 OpenAI 兼容协议（多数内网代理只支持 /chat/completions）。
_OFFICIAL_API_HOSTS: dict[LLMProvider, frozenset[str]] = {
    LLMProvider.ANTHROPIC: frozenset({"api.anthropic.com"}),
    LLMProvider.OPENAI: frozenset({"api.openai.com"}),
}

# 拉取失败时的回退白名单（docs/05 §模型列表来源）
_MODEL_WHITELIST: dict[LLMProvider, list[str]] = {
    LLMProvider.ANTHROPIC: ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5"],
    LLMProvider.OPENAI: ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
    LLMProvider.OPENAI_COMPAT: [],
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class StreamChunk:
    """complete_stream 的单帧：delta 为增量文本（可能为 ""，如纯 usage 帧），
    usage 仅在流末尾/usage 帧非 None。调用方累加 usage 即得最终用量。
    finish_reason 仅在流末帧非 None（如 length / stop / tool_calls）。
    tool_calls 仅在流末帧非 None：本轮模型请求调用的工具（OpenAI 规范形态）。
    """

    delta: str
    usage: Usage | None = None
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class LLMCompletion:
    content: str
    usage: Usage
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


# 多模态消息内容：纯文本，或 OpenAI 兼容 content parts（text / image_url）。
UserContent = str | list[dict[str, Any]]

# 多轮消息（OpenAI 规范形态）：role ∈ system/user/assistant/tool；
# assistant 消息可带 tool_calls，tool 消息带 tool_call_id + content（工具结果）。
Messages = list[dict[str, Any]]

# 工具 schema（OpenAI 规范形态）：[{"type":"function","function":{name,description,parameters}}]
ToolsSpec = list[dict[str, Any]]


def image_content_part(image: bytes, media_type: str = "image/png") -> dict[str, Any]:
    """构造 OpenAI 兼容的图片 content part（data URI，自包含不依赖外部 URL）。"""
    b64 = base64.b64encode(image).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}}


def content_text(user_msg: UserContent) -> str:
    """多模态内容的纯文本投影：图片折叠为占位符，供日志 / tracing 用。"""
    if isinstance(user_msg, str):
        return user_msg
    parts = []
    for part in user_msg:
        if part.get("type") == "text":
            parts.append(str(part.get("text", "")))
        else:
            parts.append("<image>")
    return "\n".join(p for p in parts if p)


def _to_anthropic_blocks(user_msg: UserContent) -> str | list[dict[str, Any]]:
    """OpenAI content parts → Anthropic /messages blocks（图片仅支持 base64 / url source）。"""
    if isinstance(user_msg, str):
        return user_msg
    blocks: list[dict[str, Any]] = []
    for part in user_msg:
        if part.get("type") == "text":
            blocks.append({"type": "text", "text": str(part.get("text", ""))})
        elif part.get("type") == "image_url":
            url = str((part.get("image_url") or {}).get("url", ""))
            m = re.match(r"^data:([^;]+);base64,(.+)$", url, re.DOTALL)
            if m:
                blocks.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)},
                    }
                )
            elif url:
                blocks.append({"type": "image", "source": {"type": "url", "url": url}})
    return blocks


def _tools_to_anthropic(tools: ToolsSpec) -> list[dict[str, Any]]:
    """OpenAI 工具规范 → Anthropic tools 字段（name/description/input_schema）。"""
    out: list[dict[str, Any]] = []
    for tool in tools:
        func = tool.get("function") or {}
        if not func.get("name"):
            continue
        out.append(
            {
                "name": func["name"],
                "description": str(func.get("description") or ""),
                "input_schema": func.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return out


def _tool_calls_to_anthropic_blocks(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI tool_calls → Anthropic tool_use content blocks（arguments JSON 串转 dict）。"""
    import json

    blocks: list[dict[str, Any]] = []
    for call in tool_calls:
        func = call.get("function") or {}
        try:
            args = json.loads(func.get("arguments") or "{}")
        except (ValueError, TypeError):
            args = {}
        blocks.append(
            {
                "type": "tool_use",
                "id": call.get("id") or "",
                "name": func.get("name") or "",
                "input": args if isinstance(args, dict) else {},
            }
        )
    return blocks


def _messages_to_anthropic(
    messages: Messages, system: str
) -> tuple[str, list[dict[str, Any]]]:
    """OpenAI 规范多轮消息 → Anthropic (system, messages)。

    - system 角色合并进独立 system 字段（Anthropic 不允许 system 在 messages 里）；
    - assistant.tool_calls → tool_use blocks（正文文本保留为 text block）；
    - role:"tool" → user 消息的 tool_result block（工具结果回填）。
    """
    system_parts = [system] if system else []
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            text = msg.get("content")
            if isinstance(text, str) and text.strip():
                system_parts.append(text.strip())
            continue
        if role == "tool":
            tool_content = msg.get("content")
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id") or "",
                            "content": (
                                tool_content if isinstance(tool_content, str) else ""
                            ),
                        }
                    ],
                }
            )
            continue
        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            content = msg.get("content")
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            if msg.get("tool_calls"):
                blocks.extend(_tool_calls_to_anthropic_blocks(msg["tool_calls"]))
            out.append({"role": "assistant", "content": blocks or ""})
            continue
        # user：字符串直传，parts 走 blocks 转换
        content = msg.get("content")
        if isinstance(content, list):
            out.append({"role": "user", "content": _to_anthropic_blocks(content)})
        else:
            out.append({"role": "user", "content": content or ""})
    return "\n\n".join(p for p in system_parts if p), out


def _anthropic_tool_calls(content_blocks: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Anthropic tool_use blocks → OpenAI tool_calls 规范形态（arguments 序列化为 JSON 串）。"""
    import json

    calls: list[dict[str, Any]] = []
    for block in content_blocks:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            calls.append(
                {
                    "id": block.get("id") or "",
                    "type": "function",
                    "function": {
                        "name": block.get("name") or "",
                        "arguments": json.dumps(
                            block.get("input") or {}, ensure_ascii=False
                        ),
                    },
                }
            )
    return calls or None


# 工具调用能力表：BYOK 下游能力不一（见 thinking_disable_fields 同类问题）。
# 默认三大协议族均支持 OpenAI 风格 tools / Anthropic tool_use；
# settings.llm_tools_blocklist（模型前缀逗号分隔）可按模型关掉。
_TOOLS_SUPPORT: dict[LLMProvider, bool] = {
    LLMProvider.ANTHROPIC: True,
    LLMProvider.OPENAI: True,
    LLMProvider.OPENAI_COMPAT: True,
}


def tools_supported(
    provider: LLMProvider, model: str, base_url: str | None = None
) -> bool:
    """该 provider/model 是否可绑定工具；不支持时不绑定（行为降级，不报错）。"""
    if not _TOOLS_SUPPORT.get(provider, False):
        return False
    model_name = (model or "").strip().lower()
    for prefix in settings.llm_tools_blocklist.split(","):
        prefix = prefix.strip().lower()
        if prefix and model_name.startswith(prefix):
            return False
    return True


def _host_from_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    from urllib.parse import urlparse

    return (urlparse(base_url).hostname or "").lower() or None


def _is_official_base(provider: LLMProvider, base_url: str | None) -> bool:
    if not base_url:
        return True
    host = _host_from_base_url(base_url)
    if not host:
        return False
    return host in _OFFICIAL_API_HOSTS.get(provider, frozenset())


def _uses_anthropic_native_api(provider: LLMProvider, base_url: str | None) -> bool:
    """Use Anthropic /messages for official hosts and known Anthropic-style proxies."""
    if provider != LLMProvider.ANTHROPIC:
        return False
    if _is_official_base(provider, base_url):
        return True
    if not base_url:
        return False
    return "/anthropic" in _normalize_base_url(base_url).lower()


def _auth_headers(
    provider: LLMProvider, apikey: str, base_url: str | None = None
) -> dict[str, str]:
    if _uses_anthropic_native_api(provider, base_url):
        return {"x-api-key": apikey, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {apikey}"}


_STRIP_BASE_SUFFIXES = ("/chat/completions", "/messages", "/models")


def _normalize_base_url(base_url: str) -> str:
    """去掉用户误填的 endpoint 后缀，避免拼出双重路径导致 404。"""
    base = base_url.strip().rstrip("/")
    for suffix in _STRIP_BASE_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
    return base


def _ensure_api_version_path(base: str, provider: LLMProvider) -> str:
    """域名根路径无 /v1 时补上（OpenAI 系常见约定）。"""
    from urllib.parse import urlparse

    parsed = urlparse(base)
    path = (parsed.path or "").strip("/")
    if not path:
        return f"{base}/v1"
    last = path.split("/")[-1].lower()
    if re.fullmatch(r"v\d+(?:beta\d+)?", last):
        return base
    return f"{base}/v1"


def _api_base(provider: LLMProvider, base_url: str | None) -> str:
    """解析 API 根路径；官方 provider 可省略 base_url，openai_compat 必填。"""
    if provider == LLMProvider.OPENAI_COMPAT:
        if not base_url:
            raise ValueError("openai_compat 需配置 base_url")
        base = _ensure_api_version_path(_normalize_base_url(base_url), provider)
        return base
    if base_url:
        base = _ensure_api_version_path(_normalize_base_url(base_url), provider)
        return base
    return _DEFAULT_API_BASE[provider]


def _messages_url(provider: LLMProvider, base_url: str | None) -> str:
    base = _api_base(provider, base_url)
    if _uses_anthropic_native_api(provider, base_url):
        return f"{base}/messages"
    return f"{base}/chat/completions"


def _models_list_url(provider: LLMProvider, base_url: str | None) -> str:
    return f"{_api_base(provider, base_url)}/models"


def _direct_hosts() -> list[str]:
    """配置的国内直连 host 子串（逗号分隔）。"""
    return [h.strip() for h in settings.llm_direct_hosts.split(",") if h.strip()]


def _build_llm_client(url: str, timeout: httpx.Timeout) -> httpx.AsyncClient:
    """构造 LLM httpx 客户端，按目标 host 决定是否走系统代理。

    httpx 0.28 在 Windows 上会读注册表代理（即便无 *_PROXY 环境变量），
    国内 provider（dashscope/deepseek 等）走该代理常因代理无对应出口而超时。
    命中配置的国内 host → 强制直连（trust_env=False）；其余沿用默认行为
    （trust_env=True），保留「用代理访问海外 OpenAI/Anthropic」的能力。
    """
    host = (_host_from_base_url(url) or "").lower()
    if any(h in host for h in _direct_hosts()):
        return httpx.AsyncClient(timeout=timeout, trust_env=False)
    return httpx.AsyncClient(timeout=timeout)


async def test_connectivity(
    provider: LLMProvider,
    apikey: str,
    model: str,
    base_url: str | None = None,
) -> tuple[bool, str | None]:
    """最小 completion 探测 provider + apikey + model + base_url（compat 必填）。"""
    trimmed = model.strip()
    if not trimmed:
        return False, "model 不能为空"
    if provider == LLMProvider.OPENAI_COMPAT and not base_url:
        return False, "openai_compat 需配置 base_url"
    try:
        result = await complete(
            provider,
            apikey,
            trimmed,
            "You are a connectivity probe.",
            "Reply with OK.",
            base_url=base_url,
            max_tokens=8,
        )
        if not result.content.strip():
            # 推理模型未关 thinking 时会耗尽 max_tokens，content 恒空（HTTP 200 假成功）
            return (
                False,
                "模型返回空内容：thinking 可能耗尽 max_tokens，请关闭 thinking",
            )
        return True, None
    except httpx.HTTPError as e:
        return False, f"网络错误: {e}"
    except (RuntimeError, ValueError) as e:
        return False, str(e)[:200]
    except Exception as e:  # noqa: BLE001 探测失败统一返回文案
        return False, str(e)[:200]


# 8×8 纯白 PNG：视觉连通探针用，模型必须真正读到图片才能答出「亮」
_VISION_PROBE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAD0lEQVR42mP4hQMwDC0JAEMPu4FyxXnhAAAAAElFTkSuQmCC"
)
_VISION_PROBE_OK_WORDS = ("light", "white", "bright", "亮", "白")


async def test_vision_connectivity(
    provider: LLMProvider,
    apikey: str,
    model: str,
    base_url: str | None = None,
) -> tuple[bool, str | None]:
    """探测视觉模型：发一张纯白图要求判亮暗；答不出「亮」视为不支持图片输入。

    比 test_connectivity 多一层能力校验：纯文本模型对图片 part 会 400，或忽略图片瞎答，
    两者都不能算配置成功（#160）。
    """
    trimmed = model.strip()
    if not trimmed:
        return False, "model 不能为空"
    if provider == LLMProvider.OPENAI_COMPAT and not base_url:
        return False, "openai_compat 需配置 base_url"
    try:
        result = await complete(
            provider,
            apikey,
            trimmed,
            "You are a connectivity probe for a vision model.",
            [
                {
                    "type": "text",
                    "text": (
                        "Is this image light or dark? Reply with exactly one word: light or dark."
                    ),
                },
                image_content_part(_VISION_PROBE_PNG),
            ],
            base_url=base_url,
            max_tokens=256,
            read_timeout_s=settings.visual_acceptance_timeout_s,
        )
        answer = result.content.strip()
        if not answer:
            return False, "模型返回空内容：thinking 可能耗尽 max_tokens，请关闭 thinking"
        if not any(w in answer.lower() for w in _VISION_PROBE_OK_WORDS):
            return False, f"模型未能读取图片内容（返回：{answer[:60]}），请确认是视觉模型"
        return True, None
    except httpx.HTTPError as e:
        return False, f"网络错误: {e}"
    except Exception as e:  # noqa: BLE001 探测失败统一返回文案
        return False, str(e)[:200]


async def list_models(provider: LLMProvider, apikey: str, base_url: str | None = None) -> list[str]:
    """按 provider 拉 /models；失败回退白名单（docs/05 §模型列表来源）。"""
    try:
        if provider == LLMProvider.OPENAI_COMPAT and not base_url:
            return list(_MODEL_WHITELIST[provider])
        url = _models_list_url(provider, base_url)
        headers = _auth_headers(provider, apikey, base_url)
        async with _build_llm_client(url, httpx.Timeout(10)) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            ids: list[str] = [
                str(m["id"])
                for m in resp.json().get("data", [])
                if isinstance(m, dict) and m.get("id")
            ]
            if ids:
                return ids
    except Exception:  # noqa: BLE001  # nosec B110 拉取失败走白名单
        pass
    return list(_MODEL_WHITELIST[provider])


def _build_body(
    provider: LLMProvider,
    model: str,
    system: str,
    user_msg: UserContent,
    base_url: str | None,
    *,
    max_tokens: int,
    stream: bool,
    messages: Messages | None = None,
    tools: ToolsSpec | None = None,
    tool_choice: str | None = None,
) -> dict:
    """构造 chat/messages 请求体。非流式与流式共用，仅 stream 字段不同。

    Anthropic 官方域名走原生 /messages（system 独立字段）；其余一律 OpenAI 兼容。
    user_msg 可为多模态 content parts（OpenAI 格式），Anthropic 路径自动转 blocks。
    thinking 默认关闭：见 ``thinking_disable_fields`` 厂商能力表。

    工具调用（ADR-18）：messages 提供时替代 system/user_msg 单轮构造（多轮对话含
    assistant tool_calls 与 role:"tool" 结果回填）；tools/tool_choice 仅在显式传入时
    携带——未传入的调用与既有行为完全一致（compat 端点不感知新字段）。
    """
    if _uses_anthropic_native_api(provider, base_url):
        merged_system, chat_messages = (
            _messages_to_anthropic(messages, system) if messages is not None else (
                system,
                [{"role": "user", "content": _to_anthropic_blocks(user_msg)}],
            )
        )
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": merged_system,
            "messages": chat_messages,
        }
        if tools:
            body["tools"] = _tools_to_anthropic(tools)
            if tool_choice == "auto":
                body["tool_choice"] = {"type": "auto"}
    else:
        if messages is not None:
            chat_messages = messages
        else:
            default_messages: Messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ]
            chat_messages = default_messages
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
        }
        if tools:
            body["tools"] = tools
            if tool_choice:
                body["tool_choice"] = tool_choice
        # OpenAI 兼容流式：请求末帧带 usage（标准约定）；部分 compat 实现不支持，
        # 缺失时由 complete_stream 兜底估算。
        if stream:
            body["stream_options"] = {"include_usage": True}
    body.update(thinking_disable_fields(provider, base_url, model))
    if stream:
        body["stream"] = True
    return body


def _llm_timeout(read_timeout_s: int | None = None) -> httpx.Timeout:
    """读超时远大于建连：整段代码生成（尤其推理模型）耗时长，而服务端不可达应快速失败。

    read_timeout_s 供短判定类调用（如视觉验收）覆盖默认的长读超时。
    """
    return httpx.Timeout(
        connect=settings.llm_connect_timeout,
        read=read_timeout_s if read_timeout_s is not None else settings.llm_request_timeout,
        write=settings.llm_connect_timeout,
        pool=settings.llm_connect_timeout,
    )


def _retry_delay_s(attempt: int) -> float:
    """指数退避 + 少量 jitter：attempt 从 0 起（第 1 次失败后的等待）。"""
    base = settings.llm_http_retry_base_delay_s
    return base * (2**attempt) + random.uniform(0, base)  # nosec B311


def _http_error_hint(url: str, status_code: int) -> str:
    if status_code != 404:
        return ""
    return (
        f"；请求 URL: {url}。"
        "请确认 base_url 为 API 根（如 https://api.openai.com/v1），"
        "勿含 /chat/completions；自定义代理请选 OpenAI 兼容或填写正确域名"
    )


async def _sleep_before_retry(*, attempt: int, model: str, reason: str) -> None:
    delay = _retry_delay_s(attempt)
    log.warning(
        "llm http retry",
        extra={
            "stage": "http",
            "model": model,
            "attempt": attempt + 1,
            "delay_s": round(delay, 3),
            "reason": reason,
        },
    )
    await asyncio.sleep(delay)


async def _post_with_retries(
    url: str,
    headers: dict[str, str],
    body: dict,
    timeout: httpx.Timeout,
    *,
    model: str,
    started: float,
) -> httpx.Response:
    """带传输层重试（网络错误 / 429 / 502-504 指数退避）的单次 POST。"""
    max_retries = settings.llm_http_max_retries
    last_http_error: httpx.HTTPError | None = None
    resp: httpx.Response | None = None
    for attempt in range(max_retries + 1):
        try:
            async with _build_llm_client(url, timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            last_http_error = exc
            if attempt >= max_retries:
                duration = round(time.monotonic() - started, 3)
                log.exception(
                    "llm http failed",
                    extra={"stage": "http", "model": model, "duration": duration},
                )
                raise
            await _sleep_before_retry(attempt=attempt, model=model, reason=type(exc).__name__)
            continue

        if resp.status_code in _RETRYABLE_HTTP_STATUS and attempt < max_retries:
            await _sleep_before_retry(
                attempt=attempt,
                model=model,
                reason=f"HTTP {resp.status_code}",
            )
            continue
        break
    if resp is None:
        assert last_http_error is not None
        raise last_http_error
    return resp


def _degrade_tools_on_400(
    resp: httpx.Response, tools: ToolsSpec | None
) -> bool:
    """ADR-18 运行时降级判定：绑定 tools 收到 400 → 视为端点不支持工具。

    静态能力表（tools_supported）覆盖不到的 compat 端点在此兜底：
    行为降级为无工具调用（agent 自主决策），不把能力问题抛给用户。
    """
    return resp.status_code == 400 and tools is not None


async def complete(
    provider: LLMProvider,
    apikey: str,
    model: str,
    system: str | None = None,
    user_msg: UserContent | None = None,
    base_url: str | None = None,
    *,
    max_tokens: int | None = None,
    read_timeout_s: int | None = None,
    messages: Messages | None = None,
    tools: ToolsSpec | None = None,
    tool_choice: str | None = None,
) -> LLMCompletion:
    """调一次补全，返回 (content, usage)。usage 取响应真实字段（docs/05 不估算）。

    传输层对网络错误与 429/502-504 做有限指数退避重试，不消耗业务自修复预算。
    user_msg 支持多模态 content parts（见 ``image_content_part``）。
    工具调用（ADR-18）：传 messages（多轮）与 tools 时，模型可返回 tool_calls
    （OpenAI 规范形态，list[dict]），调用方负责执行工具并回填结果；
    绑定 tools 收到 400 时自动去 tools 重试一次（运行时能力降级）。
    """
    if max_tokens is None:
        max_tokens = settings.llm_max_tokens
    headers = {**_auth_headers(provider, apikey, base_url), "content-type": "application/json"}
    url = _messages_url(provider, base_url)

    def _body(effective_tools: ToolsSpec | None) -> dict:
        return _build_body(
            provider,
            model,
            system or "",
            user_msg or "",
            base_url,
            max_tokens=max_tokens,
            stream=False,
            messages=messages,
            tools=effective_tools,
            tool_choice=tool_choice if effective_tools is not None else None,
        )

    timeout = _llm_timeout(read_timeout_s)
    # 只记 url（仅含 host+path，无 key）/model/status/duration，绝不记 headers（含 apikey）
    started = time.monotonic()
    log.info("llm http request", extra={"stage": "http", "model": model, "url": url})
    resp = await _post_with_retries(
        url, headers, _body(tools), timeout, model=model, started=started
    )
    if _degrade_tools_on_400(resp, tools):
        log.warning(
            "llm tools rejected with 400, retrying without tools (runtime degrade)",
            extra={"stage": "http", "model": model},
        )
        resp = await _post_with_retries(
            url, headers, _body(None), timeout, model=model, started=started
        )

    duration = round(time.monotonic() - started, 3)
    log.info(
        "llm http response",
        extra={
            "stage": "http",
            "model": model,
            "status": resp.status_code,
            "duration": duration,
        },
    )
    if resp.status_code != 200:
        raise AppError(
            ErrorCode.LLM_CONFIG_INVALID,
            f"LLM 调用失败 HTTP {resp.status_code}: "
            f"{resp.text[:120]}{_http_error_hint(url, resp.status_code)}",
        )
    data = resp.json()
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    if _uses_anthropic_native_api(provider, base_url):
        content_blocks = data.get("content", [])
        content = "".join(
            b.get("text", "") for b in content_blocks if isinstance(b, dict)
        )
        usage = Usage(
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
        )
        finish_reason = data.get("stop_reason")
        tool_calls = _anthropic_tool_calls(content_blocks)
    else:
        choice = data["choices"][0]
        message = choice.get("message", {})
        raw = message.get("content")
        content = raw if isinstance(raw, str) else (raw or "")
        usage = Usage(
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
        )
        finish_reason = choice.get("finish_reason")
        raw_calls = message.get("tool_calls")
        if isinstance(raw_calls, list) and raw_calls:
            tool_calls = raw_calls
    return LLMCompletion(
        content=content or "",
        usage=usage,
        finish_reason=finish_reason,
        tool_calls=tool_calls,
    )


async def _iter_sse(resp: httpx.Response) -> AsyncIterator[tuple[str | None, str]]:
    """按 SSE 协议把响应流切成 (event_name, data_json) 事件。

    一个 SSE 事件由若干行组成、以空行分隔；`event:` 行可选，`data:` 行可有多个。
    返回 (event_name, data) —— event_name 为 None 表示协议未给（OpenAI 仅有 data）。
    仅提取 data 行（多行按 \n 拼接），`[DONE]` 作为 data 原样返回交给上层判定。
    """
    event_name: str | None = None
    data_lines: list[str] = []
    async for raw_line in resp.aiter_lines():
        # aiter_lines 已去换行，但兼容 \r\n 残留的 \r
        line = raw_line.rstrip("\r")
        if line == "":
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue  # SSE 注释
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
        # 其余字段（id:/retry: 等）忽略
    # 流末尾若仍有未 flush 的事件（无结尾空行）补发一次
    if data_lines:
        yield event_name, "\n".join(data_lines)


def _parse_json(data: str) -> dict:
    import json

    return json.loads(data)


async def _parse_anthropic_stream(
    resp: httpx.Response,
) -> AsyncIterator[StreamChunk]:
    """Anthropic 原生 /messages 流式解析。

    关键事件：
    - message_start：data.message.usage.input_tokens（input 在此帧）
    - content_block_start：type==tool_use 的块开始（id/name，input 稍后增量到达）
    - content_block_delta：delta.text（正文增量）/ delta.partial_json（tool 参数增量）
    - message_delta：usage.output_tokens（output 在此帧，注意是累计终值）
    - message_stop：流结束（tool_calls 随终帧一并发出）
    """
    input_tokens = 0
    output_tokens = 0
    # tool_use 累积：block index → {id, name, args_parts}
    tool_blocks: dict[int, dict[str, Any]] = {}
    async for event_name, data in _iter_sse(resp):
        if data == "[DONE]":
            break
        try:
            obj = _parse_json(data)
        except (ValueError, TypeError):
            continue
        etype = obj.get("type") or event_name
        if etype == "message_start":
            msg_usage = (obj.get("message") or {}).get("usage") or {}
            input_tokens = msg_usage.get("input_tokens", 0)
            output_tokens = msg_usage.get("output_tokens", 0)
        elif etype == "content_block_start":
            block = obj.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool_blocks[obj.get("index", 0)] = {
                    "id": block.get("id") or "",
                    "name": block.get("name") or "",
                    "args_parts": [],
                }
        elif etype == "content_block_delta":
            delta = obj.get("delta") or {}
            # text_delta 才是正文；thinking_delta/其他丢弃（见 qwen 关 thinking 注释）
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield StreamChunk(delta=text)
            elif delta.get("type") == "input_json_delta":
                idx = obj.get("index", 0)
                if idx in tool_blocks:
                    tool_blocks[idx]["args_parts"].append(delta.get("partial_json", ""))
        elif etype == "message_delta":
            usage = obj.get("usage") or {}
            if "output_tokens" in usage:
                output_tokens = usage["output_tokens"]
        elif etype == "message_stop":

            calls = [
                {
                    "id": tb["id"],
                    "type": "function",
                    "function": {
                        "name": tb["name"],
                        "arguments": "".join(tb["args_parts"]) or "{}",
                    },
                }
                for tb in tool_blocks.values()
            ]
            yield StreamChunk(
                delta="",
                usage=Usage(input_tokens, output_tokens),
                finish_reason=obj.get("stop_reason"),
                tool_calls=calls or None,
            )
            return


async def _parse_openai_stream(
    resp: httpx.Response,
) -> AsyncIterator[StreamChunk]:
    """OpenAI 兼容 /chat/completions 流式解析。

    - data.choices[0].delta.content：正文增量（reasoning_content 丢弃）。
    - usage 单独成帧（choices 为空，需请求带 stream_options.include_usage）。
    - data: [DONE] 终止。

    若 provider 不返回 usage 帧（部分 compat 实现），上层 complete_stream 会兜底估算。
    """
    char_count = 0
    final_usage: Usage | None = None
    finish_reason: str | None = None
    # tool_calls 增量累积：index → {id, name, arguments_parts}
    tool_acc: dict[int, dict[str, Any]] = {}
    async for _event_name, data in _iter_sse(resp):
        if data == "[DONE]":
            break
        try:
            obj = _parse_json(data)
        except (ValueError, TypeError):
            continue
        usage = obj.get("usage")
        if isinstance(usage, dict):
            # 兼容 OpenAI(prompt/completion_tokens) 与部分实现(input/output_tokens)
            final_usage = Usage(
                input_tokens=usage.get("input_tokens") or usage.get("prompt_tokens") or 0,
                output_tokens=usage.get("output_tokens") or usage.get("completion_tokens") or 0,
            )
        choices = obj.get("choices") or []
        if not choices:
            continue
        choice = choices[0]
        if choice.get("finish_reason"):
            finish_reason = choice.get("finish_reason")
        delta = choice.get("delta") or {}
        # content 才是正文；reasoning_content（思考链）丢弃
        text = delta.get("content")
        if text:
            char_count += len(text)
            yield StreamChunk(delta=text)
        # tool_calls 分片：id/name 首帧到达，arguments 逐帧追加
        for frag in delta.get("tool_calls") or []:
            if not isinstance(frag, dict):
                continue
            idx = int(frag.get("index") or 0)
            slot = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments_parts": []})
            if frag.get("id"):
                slot["id"] = frag["id"]
            func = frag.get("function") or {}
            if func.get("name"):
                slot["name"] = func["name"]
            if func.get("arguments"):
                slot["arguments_parts"].append(func["arguments"])
    tool_calls = [
        {
            "id": slot["id"],
            "type": "function",
            "function": {
                "name": slot["name"],
                "arguments": "".join(slot["arguments_parts"]) or "{}",
            },
        }
        for slot in tool_acc.values()
    ] or None
    if final_usage is not None:
        yield StreamChunk(
            delta="",
            usage=final_usage,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )
    elif char_count or tool_calls:
        # 兜底：provider 没给 usage，按字符数估 output（中英混合代码 ~4 chars/token），
        # input 记 0（解析器拿不到 prompt）。与 docs「不估算」原则的已知例外
        # （compat 流式 usage 缺失），比此前按 chunk 计数更接近真实值。
        est = Usage(input_tokens=0, output_tokens=max(1, char_count // 4))
        yield StreamChunk(
            delta="",
            usage=est,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )
        log.warning(
            "llm stream usage missing, estimated by char count",
            extra={"stage": "http", "chars": char_count},
        )


async def complete_stream(
    provider: LLMProvider,
    apikey: str,
    model: str,
    system: str | None = None,
    user_msg: str | None = None,
    base_url: str | None = None,
    *,
    max_tokens: int | None = None,
    messages: Messages | None = None,
    tools: ToolsSpec | None = None,
    tool_choice: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """流式补全：逐 token yield StreamChunk，末帧带 usage（及可能的 tool_calls）。

    与 complete() 共享请求体构造（_build_body），双协议 SSE 解析各自一套。
    传输层仅在开流前对网络错误 / 429 / 502-504 重试；一旦开始 yield 不再重试，避免重复输出。
    httpx stream 在 generator 退出（含被 aclose/cancel）时自动 aclose 连接。
    """
    if max_tokens is None:
        max_tokens = settings.llm_max_tokens
    headers = {**_auth_headers(provider, apikey, base_url), "content-type": "application/json"}
    url = _messages_url(provider, base_url)

    def _body(effective_tools: ToolsSpec | None) -> dict:
        return _build_body(
            provider,
            model,
            system or "",
            user_msg or "",
            base_url,
            max_tokens=max_tokens,
            stream=True,
            messages=messages,
            tools=effective_tools,
            tool_choice=tool_choice if effective_tools is not None else None,
        )

    timeout = _llm_timeout()
    max_retries = settings.llm_http_max_retries
    started = time.monotonic()
    log.info("llm stream request", extra={"stage": "http", "model": model, "url": url})
    started_yielding = False
    effective_tools = tools
    attempt = 0
    while attempt <= max_retries:
        try:
            async with (
                _build_llm_client(url, timeout) as client,
                client.stream("POST", url, headers=headers, json=_body(effective_tools)) as resp,
            ):
                # ADR-18 运行时降级：绑定 tools 收到 400 → 端点不支持工具，
                # 去 tools 重试一次（不消耗传输层重试预算），行为降级不报错
                if (
                    resp.status_code == 400
                    and effective_tools is not None
                    and not started_yielding
                ):
                    await resp.aread()
                    log.warning(
                        "llm stream tools rejected with 400, "
                        "retrying without tools (runtime degrade)",
                        extra={"stage": "http", "model": model},
                    )
                    effective_tools = None
                    continue
                if (
                    resp.status_code in _RETRYABLE_HTTP_STATUS
                    and attempt < max_retries
                    and not started_yielding
                ):
                    await resp.aread()
                    await _sleep_before_retry(
                        attempt=attempt,
                        model=model,
                        reason=f"HTTP {resp.status_code}",
                    )
                    attempt += 1
                    continue
                if resp.status_code != 200:
                    err = (await resp.aread()).decode("utf-8", "replace")[:200]
                    raise AppError(
                        ErrorCode.LLM_CONFIG_INVALID,
                        f"LLM 流式调用失败 HTTP {resp.status_code}: {err}",
                    )
                if _uses_anthropic_native_api(provider, base_url):
                    parser = _parse_anthropic_stream(resp)
                else:
                    parser = _parse_openai_stream(resp)
                started_yielding = True
                async for chunk in parser:
                    yield chunk
                break
        except httpx.HTTPError:
            if started_yielding or attempt >= max_retries:
                duration = round(time.monotonic() - started, 3)
                log.exception(
                    "llm stream failed",
                    extra={"stage": "http", "model": model, "duration": duration},
                )
                raise
            await _sleep_before_retry(attempt=attempt, model=model, reason="HTTPError")
            attempt += 1
    duration = round(time.monotonic() - started, 3)
    log.info(
        "llm stream response done",
        extra={"stage": "http", "model": model, "duration": duration},
    )
