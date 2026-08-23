"""LLM provider 抽象：连通性测试 + complete() 调用。

docs/05 §连通性测试：保存前发最小 completion，失败不让保存。
complete() 返回 (content, usage)，usage 取响应真实字段，不估算（docs/05）。
"""

import asyncio
import logging
import random
import re
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
    """从 base_url 提取主机名（小写）。

    作用：判断官方 API、直连、thinking 参数等。
    场景：provider 内部 URL/协议分支。
    参数：base_url 可选。
    返回：hostname 或 None。
    """
    if not base_url:
        return None
    from urllib.parse import urlparse

    return (urlparse(base_url).hostname or "").lower() or None


def _is_official_base(provider: LLMProvider, base_url: str | None) -> bool:
    """判断 base_url 是否指向该 provider 官方 API 域名。

    作用：无 base_url 视为官方默认。
    场景：选择 Anthropic 原生 /messages 或 OpenAI 兼容路径。
    参数：provider、base_url。
    返回：官方域为 True。
    """
    if not base_url:
        return True
    host = _host_from_base_url(base_url)
    if not host:
        return False
    return host in _OFFICIAL_API_HOSTS.get(provider, frozenset())


def _uses_anthropic_native_api(provider: LLMProvider, base_url: str | None) -> bool:
    """是否使用 Anthropic 原生 /messages API。

    作用：官方域名或含 /anthropic 的代理走原生协议。
    场景：构造请求体与 SSE 解析分支。
    参数：provider、base_url。
    返回：使用原生 API 为 True。
    """
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
    """构造 LLM HTTP 鉴权头。

    作用：Anthropic 原生用 x-api-key；其余 Bearer。
    场景：complete/list_models 等 HTTP 请求。
    参数：provider、apikey、base_url。
    返回：headers 字典（不含 content-type）。
    """
    if _uses_anthropic_native_api(provider, base_url):
        return {"x-api-key": apikey, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {apikey}"}


_STRIP_BASE_SUFFIXES = ("/chat/completions", "/messages", "/models")


def _normalize_base_url(base_url: str) -> str:
    """去掉用户误填的 endpoint 后缀。

    作用：剥离 /chat/completions、/messages、/models 避免双重路径 404。
    场景：_api_base 解析前。
    参数：base_url 原始字符串。
    返回：规范化后的 API 根路径。
    """
    base = base_url.strip().rstrip("/")
    for suffix in _STRIP_BASE_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
    return base


def _ensure_api_version_path(base: str, provider: LLMProvider) -> str:
    """域名根路径无 /v1 时补上版本段。

    作用：OpenAI 系常见约定补 /v1。
    场景：openai_compat 自定义 base_url。
    参数：base 已 normalize 的根、provider。
    返回：带版本路径的 base URL。
    """
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
    """解析 LLM API 根 URL。

    作用：官方 provider 可省略 base_url；openai_compat 必填。
    场景：拼接 /chat/completions、/models 等。
    参数：provider、base_url。
    返回：API 根字符串；openai_compat 无 base_url 抛 ValueError。
    """
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
    """补全/流式调用的完整 endpoint URL。

    作用：Anthropic 原生 → /messages；其余 → /chat/completions。
    场景：complete、complete_stream。
    参数：provider、base_url。
    返回：完整 URL 字符串。
    """
    base = _api_base(provider, base_url)
    if _uses_anthropic_native_api(provider, base_url):
        return f"{base}/messages"
    return f"{base}/chat/completions"


def _models_list_url(provider: LLMProvider, base_url: str | None) -> str:
    """模型列表 endpoint URL。

    作用：在 API 根后拼接 /models。
    场景：list_models。
    参数：provider、base_url。
    返回：完整 URL。
    """
    return f"{_api_base(provider, base_url)}/models"


def _direct_hosts() -> list[str]:
    """读取配置的国内直连 host 子串列表。

    作用：解析 settings.llm_direct_hosts 逗号分隔项。
    场景：_build_llm_client 决定是否 trust_env=False。
    参数：无。
    返回：非空 host 子串列表。
    """
    return [h.strip() for h in settings.llm_direct_hosts.split(",") if h.strip()]


def _build_llm_client(url: str, timeout: httpx.Timeout) -> httpx.AsyncClient:
    """构造 LLM 专用 httpx 异步客户端。

    作用：国内 host 命中配置时强制直连（trust_env=False）。
    场景：complete、list_models、流式请求。
    参数：url 目标 URL（用于取 host）、timeout。
    返回：httpx.AsyncClient。
    """
    host = (_host_from_base_url(url) or "").lower()
    if any(h in host for h in _direct_hosts()):
        return httpx.AsyncClient(timeout=timeout, trust_env=False)
    return httpx.AsyncClient(timeout=timeout)


def _supports_enable_thinking(base_url: str | None, model: str) -> bool:
    """目标端点是否支持 enable_thinking 非标准参数。

    作用：仅 Qwen 模型或 DashScope host 注入该参数。
    场景：_should_disable_thinking 判断。
    参数：base_url、model。
    返回：支持为 True。
    """
    name = (model or "").lower()
    host = (_host_from_base_url(base_url) or "").lower()
    is_qwen_model = any(tok in name for tok in ("qwen", "qwq"))
    is_dashscope_host = "dashscope" in host
    return is_qwen_model or is_dashscope_host


def _requires_thinking_enabled(model: str) -> bool:
    """模型是否必须使用 enable_thinking=true。

    作用：纯推理模型（如 qwq）不可关闭 thinking。
    场景：_should_disable_thinking 排除列表。
    参数：model 模型名。
    返回：必须开启为 True。
    """
    name = (model or "").lower()
    return any(tok in name for tok in ("qwq",))


def _should_disable_thinking(provider: LLMProvider, base_url: str | None, model: str) -> bool:
    """是否应在请求体注入 enable_thinking=false。

    作用：小 max_tokens 场景避免思考 token 占满预算导致空正文。
    场景：_build_body 构造 OpenAI 兼容请求。
    参数：provider、base_url、model。
    返回：应关闭为 True。
    """
    if not settings.llm_disable_thinking:
        return False
    if _uses_anthropic_native_api(provider, base_url):
        return False
    if not _supports_enable_thinking(base_url, model):
        return False
    return not _requires_thinking_enabled(model)


def _should_disable_anthropic_thinking(provider: LLMProvider, base_url: str | None) -> bool:
    """是否应在 Anthropic 原生请求关闭 thinking 扩展。

    作用：settings.llm_disable_thinking 且走 /messages 时设 thinking.disabled。
    场景：_build_body Anthropic 分支。
    参数：provider、base_url。
    返回：应关闭为 True。
    """
    if not settings.llm_disable_thinking:
        return False
    return _uses_anthropic_native_api(provider, base_url)


async def test_connectivity(
    provider: LLMProvider,
    apikey: str,
    model: str,
    base_url: str | None = None,
) -> tuple[bool, str | None]:
    """最小 completion 探测连通性。

    作用：发极短补全验证 provider/apikey/model/base_url。
    场景：保存配置前、services.test_*。
    参数：provider、apikey、model、base_url。
    返回：(成功, None) 或 (False, 错误文案)。
    """
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
    """拉取可用模型 id 列表。

    作用：GET /models；失败回退内置白名单。
    场景：配置页模型下拉、list_models_for_user。
    参数：provider、apikey、base_url。
    返回：模型 id 字符串列表。
    """
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
    """构造 chat/messages 请求 JSON 体。

    作用：非流式与流式共用；处理 thinking 关闭与 stream_options。
    场景：complete、complete_stream POST 前。
    参数：provider、model、system、user_msg、base_url、max_tokens、stream。
    返回：请求 body 字典。
    """
    if _uses_anthropic_native_api(provider, base_url):
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }
        if _should_disable_anthropic_thinking(provider, base_url):
            body["thinking"] = {"type": "disabled"}
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
    """LLM HTTP 读/连超时配置。

    作用：读超时较长适配长生成；连超时较短快速失败。
    场景：complete、complete_stream。
    参数：无。
    返回：httpx.Timeout 对象。
    """
    return httpx.Timeout(
        connect=settings.llm_connect_timeout,
        read=settings.llm_request_timeout,
        write=settings.llm_connect_timeout,
        pool=settings.llm_connect_timeout,
    )


def _retry_delay_s(attempt: int) -> float:
    """HTTP 重试指数退避延迟（含 jitter）。

    作用：attempt 从 0 起，基数 settings.llm_http_retry_base_delay_s。
    场景：_sleep_before_retry。
    参数：attempt 当前失败次数（0-based）。
    返回：等待秒数 float。
    """
    base = settings.llm_http_retry_base_delay_s
    return base * (2**attempt) + random.uniform(0, base)  # nosec B311


def _http_error_hint(url: str, status_code: int) -> str:
    """HTTP 错误时的 base_url 排查提示。

    作用：404 时附加 URL 与 base_url 填写说明。
    场景：complete 非 200 响应。
    参数：url 请求 URL、status_code。
    返回：附加提示字符串（可能为空）。
    """
    if status_code != 404:
        return ""
    return (
        f"；请求 URL: {url}。"
        "请确认 base_url 为 API 根（如 https://api.openai.com/v1），"
        "勿含 /chat/completions；自定义代理请选 OpenAI 兼容或填写正确域名"
    )


async def _sleep_before_retry(*, attempt: int, model: str, reason: str) -> None:
    """记录重试日志并按退避策略 sleep。

    作用：传输层可重试错误（429/502-504、网络错误）等待后重试。
    场景：complete、complete_stream 重试循环内。
    参数：attempt、model、reason。
    返回：None（async sleep）。
    """
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
    """执行一次非流式 LLM 补全。

    作用：POST 补全并解析 content/usage/finish_reason；有限 HTTP 重试。
    场景：call_llm、test_connectivity、platform_complete。
    参数：provider、apikey、model、system、user_msg、base_url、max_tokens。
    返回：LLMCompletion。
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
    """解析 LLM 返回的 JSON 字符串为 dict。

    场景：provider 解析结构化输出。
    参数：data - JSON 文本。
    返回：解析后的 dict。
    """
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
