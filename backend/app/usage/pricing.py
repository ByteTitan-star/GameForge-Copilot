"""LLM 公开价表 → USD 估算（B3）。仅用于展示，计量仍以真实 usage 为准。"""

from __future__ import annotations

from dataclasses import dataclass

from app.enums import LLMProvider

# USD per 1M tokens (input, output) — 公开价近似值，可 env 覆盖扩展
_DEFAULT_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-3-5-sonnet"): (3.0, 15.0),
    ("anthropic", "claude-3-5-haiku"): (0.8, 4.0),
    ("openai", "gpt-4o"): (2.5, 10.0),
    ("openai", "gpt-4o-mini"): (0.15, 0.6),
    ("openai_compat", "default"): (1.0, 3.0),
}


@dataclass(frozen=True)
class PricePerMillion:
    input_usd: float
    output_usd: float


def price_for(provider: LLMProvider | str, model: str) -> PricePerMillion:
    prov = provider.value if isinstance(provider, LLMProvider) else str(provider)
    key = (prov, model)
    if key in _DEFAULT_TABLE:
        inp, out = _DEFAULT_TABLE[key]
        return PricePerMillion(inp, out)
    # provider 级 fallback
    fallback = _DEFAULT_TABLE.get((prov, "default"))
    if fallback:
        inp, out = fallback
        return PricePerMillion(inp, out)
    return PricePerMillion(1.0, 3.0)


def estimate_usd(
    provider: LLMProvider | str,
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    p = price_for(provider, model)
    return (input_tokens * p.input_usd + output_tokens * p.output_usd) / 1_000_000
