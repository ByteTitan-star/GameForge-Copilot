"""默认关闭模型 thinking / reasoning 的厂商能力表。

目标：所有可关闭的模型默认不开 thinking，避免思考 token 吃光 max_tokens
导致 content 为空。协议因厂商而异，禁止对未知模型盲注字段。
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.enums import LLMProvider


def _host(base_url: str | None) -> str:
    if not base_url:
        return ""
    from urllib.parse import urlparse

    return (urlparse(base_url).hostname or "").lower()


def _norm_model(model: str) -> str:
    return (model or "").lower().replace("_", "-")


def _uses_anthropic_native(provider: LLMProvider, base_url: str | None) -> bool:
    # 与 provider._uses_anthropic_native_api 对齐，避免循环导入只做轻量判定。
    if provider != LLMProvider.ANTHROPIC:
        return False
    if not base_url:
        return True
    host = _host(base_url)
    if host in {"api.anthropic.com"}:
        return True
    return "/anthropic" in base_url.rstrip("/").lower()


def thinking_disable_fields(
    provider: LLMProvider,
    base_url: str | None,
    model: str,
) -> dict[str, Any]:
    """返回应合并进 LLM 请求体的关 thinking 字段；空 dict=不注入。"""
    if not settings.llm_disable_thinking:
        return {}

    name = _norm_model(model)
    host = _host(base_url)

    if _uses_anthropic_native(provider, base_url):
        # claude-fable-5 等无法关闭
        if "fable" in name:
            return {}
        return {"thinking": {"type": "disabled"}}

    # MiniMax M2.x：官方无可关参数（reasoning_split 只影响展示）
    if "minimax" in name or "minimax" in host:
        return {}

    # 智谱 GLM / Z.ai
    if "glm" in name or "bigmodel.cn" in host or host == "z.ai" or host.endswith(".z.ai"):
        if "glm-5.3" in name:
            return {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}
        return {"thinking": {"type": "disabled"}}

    # DeepSeek
    if "deepseek" in name or "deepseek.com" in host:
        return {"thinking": {"type": "disabled"}}

    # 月之暗面 Kimi
    if "kimi" in name or "moonshot" in name or "moonshot" in host:
        return {"thinking": {"type": "disabled"}}

    # 字节豆包 Seed
    if "doubao" in name or "doubao" in host or "volces.com" in host or "volcengine" in host:
        return {"thinking": {"type": "disabled"}}

    # 纯推理 Qwen 变体：注入 false 会 400
    if "qwq" in name:
        return {}

    # 阿里 Qwen / DashScope
    if "qwen" in name or "dashscope" in host:
        return {"enable_thinking": False}

    # 百度 ERNIE（混合模式）
    if "ernie" in name or "qianfan" in host or "baidubce.com" in host:
        return {"enable_thinking": False}

    # OpenAI GPT-5 / o 系列（gpt-4o 等无此开关，勿盲注）
    if provider == LLMProvider.OPENAI or "openai.com" in host:
        if name.startswith(("gpt-5", "o1", "o3", "o4")):
            return {"reasoning": {"effort": "none"}}
        return {}

    # Google Gemini
    if "gemini" in name or "googleapis.com" in host or "generativelanguage" in host:
        if "gemini-3" in name:
            return {"thinkingLevel": "minimal"}
        if "gemini-2.5" in name or name.startswith("gemini-2"):
            return {"thinkingBudget": 0}
        return {"thinkingBudget": 0}

    # xAI Grok：4.3 可 none；4.5/4.6 最低 low
    if "grok" in name or host == "api.x.ai" or host.endswith(".x.ai"):
        if "grok-4.5" in name or "grok-4.6" in name:
            return {"reasoning_effort": "low"}
        return {"reasoning_effort": "none"}

    # Mistral
    if "mistral" in name or "mistral.ai" in host:
        return {"reasoning_effort": "none"}

    # DashScope 托管的其它模型名：沿用 enable_thinking（历史行为）
    if "dashscope" in host:
        return {"enable_thinking": False}

    return {}
