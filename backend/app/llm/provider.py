"""LLM provider 抽象：连通性测试 + complete() 调用。

docs/05 §连通性测试：保存前发最小 completion，失败不让保存。
complete() 返回 (content, usage)，usage 取响应真实字段，不估算（docs/05）。
"""

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import LLMProvider

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
    finish_reason 仅在流末帧非 None（如 length / stop）。
    """

    delta: str
    usage: Usage | None = None
    finish_reason: str | None = None


@dataclass
class LLMCompletion:
    content: str
    usage: Usage
    finish_reason: str | None = None


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


def _requires_thinking_enabled(model: str) -> bool:
    """纯推理模型：只允许 enable_thinking=true，注入 false 会 400。"""
    name = (model or "").lower()
    return any(tok in name for tok in ("qwq",))


def _should_disable_thinking(provider: LLMProvider, base_url: str | None, model: str) -> bool:
    """OpenAI 兼容路径默认关 thinking；Anthropic 原生与纯推理模型跳过。

    plan JSON / 审核 0|1 都不需要思考链：思考 token 会占满 max_tokens，
    且流式解析只收 content、丢弃 reasoning_content，易得到空正文。
    """
    if not settings.llm_disable_thinking:
        return False
    if _uses_anthropic_native_api(provider, base_url):
        return False
    return not _requires_thinking_enabled(model)


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
    user_msg: str,
    base_url: str | None,
    *,
    max_tokens: int,
    stream: bool,
) -> dict:
    """构造 chat/messages 请求体。非流式与流式共用，仅 stream 字段不同。

    Anthropic 官方域名走原生 /messages（system 独立字段）；其余一律 OpenAI 兼容。
    thinking 默认关闭（见 _should_disable_thinking）。
    """
    if _uses_anthropic_native_api(provider, base_url):
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }
    else:
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        }
        # OpenAI 兼容流式：请求末帧带 usage（标准约定）；部分 compat 实现不支持，
        # 缺失时由 complete_stream 兜底估算。
        if stream:
            body["stream_options"] = {"include_usage": True}
    if _should_disable_thinking(provider, base_url, model):
        body["enable_thinking"] = False
    if stream:
        body["stream"] = True
    return body


def _llm_timeout() -> httpx.Timeout:
    """读超时远大于建连：整段代码生成（尤其推理模型）耗时长，而服务端不可达应快速失败。"""
    return httpx.Timeout(
        connect=settings.llm_connect_timeout,
        read=settings.llm_request_timeout,
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


async def complete(
    provider: LLMProvider,
    apikey: str,
    model: str,
    system: str,
    user_msg: str,
    base_url: str | None = None,
    *,
    max_tokens: int | None = None,
) -> LLMCompletion:
    """调一次补全，返回 (content, usage)。usage 取响应真实字段（docs/05 不估算）。

    传输层对网络错误与 429/502-504 做有限指数退避重试，不消耗业务自修复预算。
    """
    if max_tokens is None:
        max_tokens = settings.llm_max_tokens
    headers = {**_auth_headers(provider, apikey, base_url), "content-type": "application/json"}
    url = _messages_url(provider, base_url)
    body = _build_body(
        provider, model, system, user_msg, base_url, max_tokens=max_tokens, stream=False
    )
    timeout = _llm_timeout()
    max_retries = settings.llm_http_max_retries
    # 只记 url（仅含 host+path，无 key）/model/status/duration，绝不记 headers（含 apikey）
    started = time.monotonic()
    log.info("llm http request", extra={"stage": "http", "model": model, "url": url})
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
    if _uses_anthropic_native_api(provider, base_url):
        content = "".join(b.get("text", "") for b in data.get("content", []))
        usage = Usage(
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
        )
        finish_reason = data.get("stop_reason")
    else:
        choice = data["choices"][0]
        raw = choice.get("message", {}).get("content")
        content = raw if isinstance(raw, str) else (raw or "")
        usage = Usage(
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
        )
        finish_reason = choice.get("finish_reason")
    return LLMCompletion(content=content or "", usage=usage, finish_reason=finish_reason)


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
    - content_block_delta：delta.text（正文增量）
    - message_delta：usage.output_tokens（output 在此帧，注意是累计终值）
    - message_stop：流结束
    """
    input_tokens = 0
    output_tokens = 0
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
        elif etype == "content_block_delta":
            delta = obj.get("delta") or {}
            # text_delta 才是正文；thinking_delta/其他丢弃（见 qwen 关 thinking 注释）
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield StreamChunk(delta=text)
        elif etype == "message_delta":
            usage = obj.get("usage") or {}
            if "output_tokens" in usage:
                output_tokens = usage["output_tokens"]
        elif etype == "message_stop":
            yield StreamChunk(
                delta="",
                usage=Usage(input_tokens, output_tokens),
                finish_reason=obj.get("stop_reason"),
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
    if final_usage is not None:
        yield StreamChunk(delta="", usage=final_usage, finish_reason=finish_reason)
    elif char_count:
        # 兜底：provider 没给 usage，按字符数估 output（中英混合代码 ~4 chars/token），
        # input 记 0（解析器拿不到 prompt）。与 docs「不估算」原则的已知例外
        # （compat 流式 usage 缺失），比此前按 chunk 计数更接近真实值。
        est = Usage(input_tokens=0, output_tokens=max(1, char_count // 4))
        yield StreamChunk(delta="", usage=est, finish_reason=finish_reason)
        log.warning(
            "llm stream usage missing, estimated by char count",
            extra={"stage": "http", "chars": char_count},
        )


async def complete_stream(
    provider: LLMProvider,
    apikey: str,
    model: str,
    system: str,
    user_msg: str,
    base_url: str | None = None,
    *,
    max_tokens: int | None = None,
) -> AsyncIterator[StreamChunk]:
    """流式补全：逐 token yield StreamChunk，末帧带 usage。

    与 complete() 共享请求体构造（_build_body），双协议 SSE 解析各自一套。
    传输层仅在开流前对网络错误 / 429 / 502-504 重试；一旦开始 yield 不再重试，避免重复输出。
    httpx stream 在 generator 退出（含被 aclose/cancel）时自动 aclose 连接。
    """
    if max_tokens is None:
        max_tokens = settings.llm_max_tokens
    headers = {**_auth_headers(provider, apikey, base_url), "content-type": "application/json"}
    url = _messages_url(provider, base_url)
    body = _build_body(
        provider, model, system, user_msg, base_url, max_tokens=max_tokens, stream=True
    )
    timeout = _llm_timeout()
    max_retries = settings.llm_http_max_retries
    started = time.monotonic()
    log.info("llm stream request", extra={"stage": "http", "model": model, "url": url})
    started_yielding = False
    for attempt in range(max_retries + 1):
        try:
            async with (
                _build_llm_client(url, timeout) as client,
                client.stream("POST", url, headers=headers, json=body) as resp,
            ):
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
    duration = round(time.monotonic() - started, 3)
    log.info(
        "llm stream response done",
        extra={"stage": "http", "model": model, "duration": duration},
    )
