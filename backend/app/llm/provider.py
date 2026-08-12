"""LLM provider 抽象：连通性测试 + complete() 调用。

docs/05 §连通性测试：保存前发最小 completion，失败不让保存。
complete() 返回 (content, usage)，usage 取响应真实字段，不估算（docs/05）。
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import LLMProvider

log = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}

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


class _RetryableLLMError(Exception):
    pass


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
    """Anthropic /messages 仅用于官方域名；自定义代理一律 OpenAI 兼容。"""
    if provider != LLMProvider.ANTHROPIC:
        return False
    return _is_official_base(provider, base_url)


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
    if path:
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


def _is_qwen_thinking_model(model: str) -> bool:
    """qwen3 系列（DashScope 默认开 thinking 的混合思考模型）。

    仅匹配 qwen3：qwq 等纯推理模型只允许 enable_thinking=true，注入 false 反而触发 400。
    DashScope 约定「非流式调用必须 enable_thinking=false」，而本模块 complete() 为非流式，
    故对 qwen3 关闭 thinking 既是性能优化（避免思考链拉长/触发读超时），也是调用合规。
    """
    return "qwen3" in (model or "").lower()


def _content_text(value: object) -> str:
    """Extract text from OpenAI-compatible string or content-block payloads."""
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for block in value:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _update_usage(usage: Usage, raw: object, *, anthropic: bool = False) -> None:
    if not isinstance(raw, dict):
        return
    input_key = "input_tokens" if anthropic else "prompt_tokens"
    output_key = "output_tokens" if anthropic else "completion_tokens"
    input_tokens = raw.get(input_key)
    output_tokens = raw.get(output_key)
    if isinstance(input_tokens, int):
        usage.input_tokens = input_tokens
    if isinstance(output_tokens, int):
        usage.output_tokens = output_tokens


async def _consume_stream(
    resp: httpx.Response, *, anthropic: bool
) -> tuple[str, Usage]:
    """Aggregate SSE chunks while keeping the upstream connection active."""
    if resp.status_code != 200:
        raw = await resp.aread()
        body = raw.decode(errors="replace")
        hint = ""
        if resp.status_code == 404:
            hint = (
                f"；请求 URL: {resp.request.url}。"
                "请确认 base_url 为 API 根（如 https://api.openai.com/v1），"
                "勿含 /chat/completions；自定义代理请选 OpenAI 兼容或填写正确域名"
            )
        message = f"LLM 调用失败 HTTP {resp.status_code}: {body[:120]}{hint}"
        if resp.status_code in _RETRYABLE_STATUS_CODES:
            raise _RetryableLLMError(message)
        raise AppError(ErrorCode.LLM_CONFIG_INVALID, message)

    parts: list[str] = []
    usage = Usage()
    async for raw_line in resp.aiter_lines():
        line = raw_line.strip()
        if not line or line.startswith(":") or line.startswith("event:"):
            continue
        payload = line[5:].strip() if line.startswith("data:") else line
        if payload == "[DONE]":
            break
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            log.warning("ignore malformed llm stream chunk")
            continue
        if not isinstance(data, dict):
            continue
        error = data.get("error")
        if error:
            message = error.get("message") if isinstance(error, dict) else str(error)
            code = error.get("code") if isinstance(error, dict) else None
            error_type = error.get("type") if isinstance(error, dict) else None
            retry_text = f"{code or ''} {error_type or ''} {message}".lower()
            retryable = any(
                marker in retry_text
                for marker in (
                    "temporarily unavailable",
                    "timeout",
                    "rate limit",
                    "overload",
                    "server error",
                    "upstream",
                )
            )
            stream_error = f"LLM 流式调用失败: {message}"
            if retryable:
                raise _RetryableLLMError(stream_error)
            raise AppError(ErrorCode.LLM_CONFIG_INVALID, stream_error)

        if anthropic:
            event_type = data.get("type")
            if event_type == "message_start":
                message = data.get("message")
                if isinstance(message, dict):
                    _update_usage(usage, message.get("usage"), anthropic=True)
            elif event_type == "content_block_start":
                block = data.get("content_block")
                if isinstance(block, dict):
                    parts.append(_content_text(block.get("text")))
            elif event_type == "content_block_delta":
                delta = data.get("delta")
                if isinstance(delta, dict) and delta.get("type") == "text_delta":
                    parts.append(_content_text(delta.get("text")))
            elif event_type == "message_delta":
                _update_usage(usage, data.get("usage"), anthropic=True)
            continue

        _update_usage(usage, data.get("usage"))
        choices = data.get("choices")
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict):
                parts.append(_content_text(delta.get("content")))

    content = "".join(parts)
    if not content:
        raise _RetryableLLMError("LLM 流式响应未返回文本内容")
    return content, usage


async def _stream_completion(
    url: str,
    headers: dict[str, str],
    body: dict[str, object],
    timeout: httpx.Timeout,
    *,
    anthropic: bool,
) -> tuple[str, Usage, int]:
    async with (
        _build_llm_client(url, timeout) as client,
        client.stream("POST", url, headers=headers, json=body) as resp,
    ):
        content, usage = await _consume_stream(resp, anthropic=anthropic)
        return content, usage, resp.status_code


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
        await complete(
            provider,
            apikey,
            trimmed,
            "You are a connectivity probe.",
            "Reply with OK.",
            base_url=base_url,
            max_tokens=8,
        )
        return True, None
    except httpx.HTTPError as e:
        return False, f"网络错误: {e}"
    except (RuntimeError, ValueError) as e:
        return False, str(e)[:200]
    except Exception as e:  # noqa: BLE001 探测失败统一返回文案
        return False, str(e)[:200]


async def list_models(
    provider: LLMProvider, apikey: str, base_url: str | None = None
) -> list[str]:
    """按 provider 拉 /models；失败回退白名单（docs/05 §模型列表来源）。"""
    try:
        if provider == LLMProvider.OPENAI_COMPAT and not base_url:
            return list(_MODEL_WHITELIST[provider])
        url = _models_list_url(provider, base_url)
        headers = _auth_headers(provider, apikey, base_url)
        async with _build_llm_client(url, httpx.Timeout(10)) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            ids = [
                m.get("id")
                for m in resp.json().get("data", [])
                if isinstance(m, dict) and m.get("id")
            ]
            if ids:
                return ids
    except Exception:  # noqa: BLE001 拉取失败走白名单
        pass
    return list(_MODEL_WHITELIST[provider])


async def complete(
    provider: LLMProvider,
    apikey: str,
    model: str,
    system: str,
    user_msg: str,
    base_url: str | None = None,
    *,
    max_tokens: int | None = None,
) -> tuple[str, Usage]:
    """调一次补全，返回 (content, usage)。usage 取响应真实字段（docs/05 不估算）。"""
    if max_tokens is None:
        max_tokens = settings.llm_max_tokens
    headers = {**_auth_headers(provider, apikey, base_url), "content-type": "application/json"}
    url = _messages_url(provider, base_url)
    anthropic_native = _uses_anthropic_native_api(provider, base_url)
    if anthropic_native:
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
            "stream": True,
        }
    else:
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        }
        if _is_official_base(provider, base_url):
            body["stream_options"] = {"include_usage": True}
    # qwen3 默认开 thinking 会拉长代码生成、易触发读超时；DashScope 非流式调用也要求
    # enable_thinking=false。命中 qwen3 则按配置关闭（仅 OpenAI 兼容路径）。
    if (
        not _uses_anthropic_native_api(provider, base_url)
        and settings.llm_disable_thinking
        and _is_qwen_thinking_model(model)
    ):
        body["enable_thinking"] = False
    # 读超时远大于建连：整段代码生成（尤其推理模型）耗时长，而服务端不可达应快速失败
    timeout = httpx.Timeout(
        connect=settings.llm_connect_timeout,
        read=settings.llm_request_timeout,
        write=settings.llm_connect_timeout,
        pool=settings.llm_connect_timeout,
    )
    # 只记 url（仅含 host+path，无 key）/model/status/duration，绝不记 headers（含 apikey）
    started = time.monotonic()
    log.info("llm http request", extra={"stage": "http", "model": model, "url": url})
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            content, usage, status_code = await _stream_completion(
                url,
                headers,
                body,
                timeout,
                anthropic=anthropic_native,
            )
            break
        except (httpx.HTTPError, _RetryableLLMError) as exc:
            last_error = exc
            if attempt == _MAX_ATTEMPTS:
                duration = round(time.monotonic() - started, 3)
                log.exception(
                    "llm http failed after retries",
                    extra={
                        "stage": "http",
                        "model": model,
                        "duration": duration,
                        "attempt": attempt,
                    },
                )
                raise AppError(
                    ErrorCode.LLM_CONFIG_INVALID,
                    f"LLM 调用在重试 {_MAX_ATTEMPTS} 次后失败: {exc}",
                ) from exc
            delay = 2 ** (attempt - 1)
            log.warning(
                "llm call retry",
                extra={
                    "stage": "http",
                    "model": model,
                    "attempt": attempt,
                    "retry_in": delay,
                },
            )
            await asyncio.sleep(delay)
    else:  # pragma: no cover - loop always breaks or raises
        raise RuntimeError("LLM retry loop ended unexpectedly") from last_error
    duration = round(time.monotonic() - started, 3)
    log.info(
        "llm http response",
        extra={
            "stage": "http",
            "model": model,
            "status": status_code,
            "duration": duration,
        },
    )
    return content, usage
