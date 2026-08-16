"""Playtest 失败诊断：调用 QA_PROMPT，失败时回落结构化 JSON（规格 §5.3）。"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.forge.design_doc import design_doc_to_text
from app.forge.prompts import build_qa_prompt

LlmCall = Callable[[str, str], Awaitable[str]]


def fallback_diagnosis(errors: list[str]) -> str:
    """LLM 不可用时的确定性诊断，禁止夹带 C 档玩法文案。"""
    return json.dumps(
        {
            "summary": "QA 诊断模型调用失败，依据确定性运行证据继续修复",
            "root_causes": list(errors) or ["自动试玩未通过"],
            "required_fixes": [
                {
                    "priority": "P0",
                    "location": "根据运行时错误定位",
                    "change": "修复上述加载/运行/交互错误",
                    "expected_result": "B 档冒烟通过",
                }
            ],
            "regression_checks": [
                "页面成功加载",
                "ArrowRight / Space 注入不崩溃",
                "无 pageerror",
                "存在运行弱信号",
            ],
        },
        ensure_ascii=False,
    )


def _evidence_block(
    *,
    errors: list[str],
    console_logs: list[str],
    source_excerpt: str,
) -> str:
    return (
        "【自动试玩错误】\n"
        f"{json.dumps(errors, ensure_ascii=False, indent=2)}\n\n"
        "【控制台日志】\n"
        f"{chr(10).join(console_logs[:20])[:6000] or '无控制台日志'}\n\n"
        "【当前 HTML 源码（data URI 已省略）】\n"
        f"{source_excerpt or '源码不可用'}"
    )


async def diagnose_playtest_failure(
    *,
    llm: LlmCall,
    design_doc: dict[str, Any] | None,
    errors: list[str],
    console_logs: list[str],
    source_excerpt: str,
    memory_prefix: str | None = None,
    failure_kind: str = "product",
) -> str:
    """根据试玩证据生成修复诊断；LLM 异常时返回 fallback JSON。

    P5：``memory_prefix`` 应由 ContextBuilder 提供；证据块仍为任务载荷。
    """
    evidence = _evidence_block(
        errors=errors, console_logs=console_logs, source_excerpt=source_excerpt
    )
    if memory_prefix:
        diagnosis_input = f"{memory_prefix}\n\n{evidence}"
    else:
        design_block = (
            "【已确认设计稿 JSON】\n" + design_doc_to_text(design_doc or {})
        )
        diagnosis_input = f"{design_block}\n\n{evidence}"
    try:
        return await llm(build_qa_prompt(failure_kind=failure_kind), diagnosis_input)
    except Exception:  # noqa: BLE001 诊断为增强项，不得阻断确定性重试
        return fallback_diagnosis(errors)
