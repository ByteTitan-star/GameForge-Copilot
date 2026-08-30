"""Code 阶段 LLM 输出截断检测与续写。

【本文件 = CodeQaLoop 阅读顺序第 6 步下半 · 约 7min】
────────────────────────────────────────
与子图的接点（必须记住）：
  OUTPUT_TRUNCATED_ERROR 写入 playtest_errors
  → after_code_or_repair 里 is_output_truncated_error → 走 "retry"
  → 直接再 code_or_repair，不进 diagnose

本文件其余：generate_code_output 内部的续写轮次；时间紧可只看
is_output_truncated_error / OUTPUT_TRUNCATED_ERROR 两个符号。
下一文件：reliability/policy.py（第 7 步）。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import settings
from app.llm.provider import LLMCompletion

_LENGTH_FINISH_REASONS = frozenset({"length", "max_tokens"})

_CONTINUATION_NOTICE = (
    "【输出截断续写】\n"
    "上一段生成因 token 上限被截断。请从下列已生成内容的末尾无缝继续，"
    "补全至完整可运行产物。\n"
    "要求：\n"
    "1. 不要重复已生成部分\n"
    "2. 只输出需要追加的剩余内容（从截断处继续）\n"
    "3. 若为 HTML，必须补全至 </html> 并确保 init() 等入口可执行\n"
    "4. 若为 project JSON，必须补全闭合括号并包含完整 files"
)

OUTPUT_TRUNCATED_ERROR = "OUTPUT_TRUNCATED: LLM output hit token limit after continuation rounds"


class OutputTruncatedError(Exception):
    """Code/Vite 生成在续写轮次耗尽后仍被截断。"""

    def __init__(self, message: str = OUTPUT_TRUNCATED_ERROR) -> None:
        super().__init__(message)


def is_output_truncated_error(errors: list[str] | None) -> bool:
    """供 code_qa_loop.after_code_or_repair 判断是否走 retry 边。"""
    if not errors:
        return False
    prefix = "OUTPUT_TRUNCATED:"
    return any(str(e).startswith(prefix) for e in errors)


def is_likely_truncated(
    content: str,
    *,
    output_tokens: int,
    max_tokens: int,
    finish_reason: str | None,
) -> bool:
    """判断是否疑似因 max_tokens 截断。"""
    if finish_reason in _LENGTH_FINISH_REASONS:
        return True
    if max_tokens > 0 and output_tokens >= int(max_tokens * 0.98):
        return True
    return has_incomplete_structure(content)


def has_incomplete_structure(content: str) -> bool:
    text = content.strip()
    if not text:
        return False
    lower = text.lower()
    if text.startswith("{") or '"format"' in text[:300]:
        try:
            json.loads(text)
        except json.JSONDecodeError:
            if text.count("{") > text.count("}"):
                return True
            if text.count("[") > text.count("]"):
                return True
            if not text.rstrip().endswith("}"):
                return True
    if "<html" in lower or "<!doctype" in lower:
        if "</html>" not in lower:
            return True
        if lower.count("<script") > lower.count("</script"):
            return True
    return False


def _looks_like_full_rewrite(suffix: str) -> bool:
    stripped = suffix.lstrip()
    if not stripped:
        return False
    lower = stripped.lower()
    return (
        lower.startswith("<!doctype")
        or lower.startswith("<html")
        or (stripped.startswith("{") and '"format"' in stripped[:300])
    )


def merge_continuation(prefix: str, suffix: str, *, max_overlap: int = 500) -> str:
    """拼接续写内容，去除 prefix 尾部与 suffix 头部的重复重叠。"""
    if not suffix:
        return prefix
    if not prefix:
        return suffix
    if _looks_like_full_rewrite(suffix):
        return suffix
    head = prefix.strip()[: min(120, len(prefix))]
    if suffix.strip().startswith(head):
        return suffix
    max_check = min(max_overlap, len(prefix), len(suffix))
    for overlap in range(max_check, 0, -1):
        if prefix[-overlap:] == suffix[:overlap]:
            return prefix + suffix[overlap:]
    return prefix + suffix


def build_continuation_user_msg(
    partial_content: str,
    *,
    context_summary: str | None = None,
    tail_chars: int | None = None,
) -> str:
    """续写轮 user message：仅续写指令 + 可选任务摘要 + 已生成尾部（不含首轮完整 prompt）。"""
    tail_limit = tail_chars or settings.llm_continuation_tail_chars
    tail = partial_content[-tail_limit:] if len(partial_content) > tail_limit else partial_content
    parts = [_CONTINUATION_NOTICE]
    if context_summary:
        parts.append(f"【任务摘要】\n{context_summary.strip()}")
    parts.append(f"【已生成内容末尾（从此处继续）】\n{tail}")
    return "\n\n".join(parts)


async def generate_with_continuation(
    llm_call: Callable[[str, str], Awaitable[LLMCompletion]],
    *,
    system: str,
    user_msg: str,
    max_tokens: int | None = None,
    max_rounds: int | None = None,
    context_summary: str | None = None,
) -> tuple[str, bool]:
    """带截断续写的 LLM 生成。返回 (content, truncated_exhausted)。"""
    limit = max_tokens if max_tokens is not None else settings.llm_code_max_tokens
    rounds = max_rounds if max_rounds is not None else settings.llm_continuation_max_rounds
    accumulated = ""
    current_user = user_msg
    last_result: LLMCompletion | None = None

    for round_idx in range(rounds + 1):
        last_result = await llm_call(system, current_user)
        piece = last_result.content
        accumulated = piece if round_idx == 0 else merge_continuation(accumulated, piece)
        if not is_likely_truncated(
            accumulated,
            output_tokens=last_result.usage.output_tokens,
            max_tokens=limit,
            finish_reason=last_result.finish_reason,
        ):
            return accumulated, False
        if round_idx >= rounds:
            return accumulated, True
        current_user = build_continuation_user_msg(
            accumulated,
            context_summary=context_summary,
        )

    assert last_result is not None
    return accumulated, True


async def generate_code_output(
    ctx: Any,
    system: str,
    user_msg: str,
    *,
    context_summary: str | None = None,
    emit_delta: bool = False,
    kind: str | None = None,
) -> tuple[str, bool]:
    """Code 阶段专用：高 max_tokens + 截断续写。返回 (content, truncated_exhausted)。"""
    from app.forge.guard import run_streamed_llm_result
    from app.llm import client as llm_client

    max_tokens = settings.llm_code_max_tokens
    phase = "code"
    llm_kind = kind or phase

    async def llm_once(sys: str, usr: str) -> LLMCompletion:
        if settings.stream_enabled:
            return await run_streamed_llm_result(
                ctx,
                sys,
                usr,
                phase=phase,
                emit_delta=emit_delta,
                kind=llm_kind,
                max_tokens=max_tokens,
            )
        result, _prov = await llm_client.call_llm(
            ctx.s,
            ctx.r,
            ctx.run.user_id,
            ctx.run.llm_config_id,
            sys,
            usr,
            game_id=ctx.game.id,
            run_id=ctx.run.id,
            kind=llm_kind,
            max_tokens=max_tokens,
        )
        return result

    return await generate_with_continuation(
        llm_once,
        system=system,
        user_msg=user_msg,
        max_tokens=max_tokens,
        context_summary=context_summary,
    )
