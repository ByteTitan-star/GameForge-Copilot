"""LLM 截断检测与续写单测。"""

from __future__ import annotations

import pytest

from app.forge.llm_continuation import (
    generate_with_continuation,
    has_incomplete_structure,
    is_likely_truncated,
    merge_continuation,
)
from app.llm.provider import LLMCompletion, Usage


def test_has_incomplete_html_without_closing_tag() -> None:
    html = "<!DOCTYPE html><html><body><script>function init(){}"
    assert has_incomplete_structure(html) is True


def test_complete_html_not_incomplete() -> None:
    html = "<!DOCTYPE html><html><body></body></html>"
    assert has_incomplete_structure(html) is False


def test_is_likely_truncated_by_finish_reason() -> None:
    assert (
        is_likely_truncated(
            "ok",
            output_tokens=100,
            max_tokens=8192,
            finish_reason="length",
        )
        is True
    )


def test_is_likely_truncated_by_output_token_ceiling() -> None:
    assert (
        is_likely_truncated(
            "<html></html>",
            output_tokens=8190,
            max_tokens=8192,
            finish_reason="stop",
        )
        is True
    )


def test_merge_continuation_deduplicates_overlap() -> None:
    prefix = "abcdef"
    suffix = "defghi"
    assert merge_continuation(prefix, suffix) == "abcdefghi"


@pytest.mark.asyncio
async def test_generate_with_continuation_stops_when_complete() -> None:
    calls = {"n": 0}

    async def llm_call(_system: str, _user: str) -> LLMCompletion:
        calls["n"] += 1
        return LLMCompletion(
            content="<!DOCTYPE html><html></html>",
            usage=Usage(output_tokens=100),
            finish_reason="stop",
        )

    content, exhausted = await generate_with_continuation(
        llm_call,
        system="sys",
        user_msg="make game",
        max_tokens=8192,
        max_rounds=3,
    )
    assert exhausted is False
    assert calls["n"] == 1
    assert "</html>" in content


@pytest.mark.asyncio
async def test_generate_with_continuation_retries_on_truncation() -> None:
    calls = {"n": 0}
    user_prompts: list[str] = []

    async def llm_call(_system: str, user: str) -> LLMCompletion:
        calls["n"] += 1
        user_prompts.append(user)
        if calls["n"] == 1:
            return LLMCompletion(
                content="<!DOCTYPE html><html><body><script>",
                usage=Usage(output_tokens=8192),
                finish_reason="length",
            )
        return LLMCompletion(
            content="</script></body></html>",
            usage=Usage(output_tokens=50),
            finish_reason="stop",
        )

    content, exhausted = await generate_with_continuation(
        llm_call,
        system="sys",
        user_msg="make game",
        max_tokens=8192,
        max_rounds=3,
    )
    assert exhausted is False
    assert calls["n"] == 2
    assert content.endswith("</html>")
    assert "截断续写" in user_prompts[1]
