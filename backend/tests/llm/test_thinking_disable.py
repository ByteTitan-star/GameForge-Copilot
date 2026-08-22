"""厂商关 thinking 能力表：默认关闭，按官方协议注入，未知/不可关则不注入。"""

from __future__ import annotations

import pytest

from app.enums import LLMProvider
from app.llm import provider
from app.llm import thinking as th


@pytest.fixture(autouse=True)
def _enable_disable_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provider.settings, "llm_disable_thinking", True)
    monkeypatch.setattr(th.settings, "llm_disable_thinking", True)


@pytest.mark.parametrize(
    ("provider", "model", "base_url", "expect"),
    [
        (
            LLMProvider.OPENAI_COMPAT,
            "glm-5.1",
            "https://open.bigmodel.cn/api/coding/paas/v4",
            {"thinking": {"type": "disabled"}},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "glm-5.3",
            "https://open.bigmodel.cn/api/paas/v4",
            {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "deepseek-v4-flash",
            "https://api.deepseek.com",
            {"thinking": {"type": "disabled"}},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "qwen3.8-max",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            {"enable_thinking": False},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "kimi-k2.5",
            "https://api.moonshot.cn/v1",
            {"thinking": {"type": "disabled"}},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "doubao-seed-2.0-pro",
            "https://ark.cn-beijing.volces.com/api/v3",
            {"thinking": {"type": "disabled"}},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "ernie-5.1",
            "https://qianfan.baidubce.com/v2",
            {"enable_thinking": False},
        ),
        (
            LLMProvider.OPENAI,
            "gpt-5.6",
            None,
            {"reasoning": {"effort": "none"}},
        ),
        (
            LLMProvider.ANTHROPIC,
            "claude-sonnet-5",
            None,
            {"thinking": {"type": "disabled"}},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "gemini-2.5-flash",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            {"thinkingBudget": 0},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "gemini-3.5-flash",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            {"thinkingLevel": "minimal"},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "grok-4.3",
            "https://api.x.ai/v1",
            {"reasoning_effort": "none"},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "grok-4.6",
            "https://api.x.ai/v1",
            {"reasoning_effort": "low"},
        ),
        (
            LLMProvider.OPENAI_COMPAT,
            "mistral-medium-3-5",
            "https://api.mistral.ai/v1",
            {"reasoning_effort": "none"},
        ),
    ],
)
def test_thinking_disable_matrix(
    provider: LLMProvider,
    model: str,
    base_url: str | None,
    expect: dict,
) -> None:
    assert th.thinking_disable_fields(provider, base_url, model) == expect


@pytest.mark.parametrize(
    ("provider", "model", "base_url"),
    [
        (LLMProvider.OPENAI_COMPAT, "MiniMax-M2.5", "https://api.minimax.chat/v1"),
        (LLMProvider.ANTHROPIC, "claude-fable-5", None),
        (LLMProvider.OPENAI_COMPAT, "qwq-32b", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        (LLMProvider.OPENAI, "gpt-4o", None),
        (LLMProvider.OPENAI_COMPAT, "unknown-model", "https://api.unknown-llm.example/v1"),
    ],
)
def test_thinking_disable_skips_when_unsupported_or_unknown(
    provider: LLMProvider,
    model: str,
    base_url: str | None,
) -> None:
    assert th.thinking_disable_fields(provider, base_url, model) == {}


def test_thinking_disable_respects_global_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(th.settings, "llm_disable_thinking", False)
    assert (
        th.thinking_disable_fields(
            LLMProvider.OPENAI_COMPAT,
            "https://api.deepseek.com",
            "deepseek-v4-flash",
        )
        == {}
    )
