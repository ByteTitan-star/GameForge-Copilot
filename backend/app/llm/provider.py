"""LLM provider 抽象：连通性测试 + complete() 调用。

docs/05 §连通性测试：保存前发最小请求，失败不让保存。
complete() 返回 (content, usage)，usage 取响应真实字段，不估算（docs/05）。
"""

from dataclasses import dataclass

import httpx

from app.enums import LLMProvider

_MODELS_URL = {
    LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1/messages",
    LLMProvider.OPENAI: "https://api.openai.com/v1/chat/completions",
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


def _auth_headers(provider: LLMProvider, apikey: str) -> dict[str, str]:
    if provider == LLMProvider.ANTHROPIC:
        return {"x-api-key": apikey, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {apikey}"}


async def test_connectivity(
    provider: LLMProvider, apikey: str, base_url: str | None = None
) -> tuple[bool, str | None]:
    """返回 (ok, error)。openai_compat 需 base_url 才测；其余调 /v1/models。"""
    if provider == LLMProvider.OPENAI_COMPAT:
        if not base_url:
            return False, "openai_compat 需配置 base_url"
        headers = _auth_headers(provider, apikey)
        url = f"{base_url.rstrip('/')}/models"
    else:
        headers = _auth_headers(provider, apikey)
        url = {
            LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1/models",
            LLMProvider.OPENAI: "https://api.openai.com/v1/models",
        }[provider]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as e:
        return False, f"网络错误: {e}"
    if resp.status_code == 200:
        return True, None
    return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


async def list_models(
    provider: LLMProvider, apikey: str, base_url: str | None = None
) -> list[str]:
    """按 provider 拉 /models；失败回退白名单（docs/05 §模型列表来源）。"""
    try:
        if provider == LLMProvider.OPENAI_COMPAT:
            if not base_url:
                return list(_MODEL_WHITELIST[provider])
            url = f"{base_url.rstrip('/')}/models"
        elif provider == LLMProvider.ANTHROPIC:
            url = "https://api.anthropic.com/v1/models"
        else:
            url = "https://api.openai.com/v1/models"
        headers = _auth_headers(provider, apikey)
        async with httpx.AsyncClient(timeout=10) as client:
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
) -> tuple[str, Usage]:
    """调一次补全，返回 (content, usage)。usage 取响应真实字段（docs/05 不估算）。"""
    headers = {**_auth_headers(provider, apikey), "content-type": "application/json"}
    if provider == LLMProvider.ANTHROPIC:
        body = {
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }
        url = _MODELS_URL[LLMProvider.ANTHROPIC]
    else:  # openai / openai_compat（compat 用 base_url）
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        }
        if provider == LLMProvider.OPENAI_COMPAT:
            if not base_url:
                raise RuntimeError("openai_compat 需配置 base_url")
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = _MODELS_URL[LLMProvider.OPENAI]
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM 调用失败 HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if provider == LLMProvider.ANTHROPIC:
        content = "".join(b.get("text", "") for b in data.get("content", []))
        usage = Usage(
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
        )
    else:
        content = data["choices"][0]["message"]["content"]
        usage = Usage(
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
        )
    return content, usage

