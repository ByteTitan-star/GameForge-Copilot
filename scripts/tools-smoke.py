#!/usr/bin/env python3
"""ADR-18 原生工具调用真实端点冒烟（单测全为 MockTransport，本脚本补真实 API 验证）。

用法（在仓库根目录）：
  SMOKE_PROVIDER=openai_compat \\
  SMOKE_BASE_URL=https://api.deepseek.com/v1 \\
  SMOKE_MODEL=deepseek-chat \\
  SMOKE_APIKEY=sk-... \\
  backend/.venv/bin/python scripts/tools-smoke.py

验证三件事：
  1) 端点接受 OpenAI 风格 tools 字段（不被 400 拒绝）；
  2) 模型能对"必须澄清"的 prompt 发起 ask_user 工具调用（返回 tool_calls）；
  3) 流式路径同样能聚合出 tool_calls。

退出码：0=全部通过；1=工具不可用（能力降级路径生效或端点拒绝）；
2=配置缺失。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.enums import LLMProvider  # noqa: E402
from app.forge.tools import ASK_USER_TOOL_SCHEMA  # noqa: E402
from app.llm import provider  # noqa: E402

PROVIDER = os.environ.get("SMOKE_PROVIDER", "openai_compat")
MODEL = os.environ.get("SMOKE_MODEL", "")
APIKEY = os.environ.get("SMOKE_APIKEY", "")
BASE_URL = os.environ.get("SMOKE_BASE_URL", "") or None

# 刻意模糊的提问：题材方向完全未定，且明确告知不许自行决定 → 应触发 ask_user
AMBIGUOUS_PROMPT = (
    "我要做一个新游戏，但还没想好题材方向。请用 ask_user 工具问我一个问题，"
    "在选项里给出两个候选题材。不要直接输出设计方案。"
)


async def smoke_non_stream() -> bool:
    result = await provider.complete(
        LLMProvider(PROVIDER),
        APIKEY,
        MODEL,
        "你是游戏策划助手。",
        AMBIGUOUS_PROMPT,
        base_url=BASE_URL,
        max_tokens=512,
        tools=[ASK_USER_TOOL_SCHEMA],
        tool_choice="auto",
    )
    print(f"[non-stream] finish_reason={result.finish_reason}")
    print(f"[non-stream] content={result.content[:120]!r}")
    if result.tool_calls:
        for call in result.tool_calls:
            name = call["function"]["name"]
            print(f"[non-stream] tool_call: {name} args={call['function']['arguments'][:200]}")
        return True
    print("[non-stream] no tool_calls returned")
    return False


async def smoke_stream() -> bool:
    chunks = []
    async for chunk in provider.complete_stream(
        LLMProvider(PROVIDER),
        APIKEY,
        MODEL,
        "你是游戏策划助手。",
        AMBIGUOUS_PROMPT,
        base_url=BASE_URL,
        max_tokens=512,
        tools=[ASK_USER_TOOL_SCHEMA],
        tool_choice="auto",
    ):
        chunks.append(chunk)
    final = next((c for c in chunks if c.tool_calls), None)
    text = "".join(c.delta for c in chunks)
    print(f"[stream] text={text[:120]!r}")
    if final is not None and final.tool_calls:
        for call in final.tool_calls:
            print(f"[stream] tool_call: {call['function']['name']}")
        return True
    print("[stream] no tool_calls aggregated")
    return False


async def main() -> int:
    if not MODEL or not APIKEY:
        print(
            "缺少 SMOKE_MODEL / SMOKE_APIKEY（可选 SMOKE_PROVIDER / SMOKE_BASE_URL）",
            file=sys.stderr,
        )
        return 2
    print(f"smoke: provider={PROVIDER} model={MODEL} base_url={BASE_URL}")
    try:
        ok_non_stream = await smoke_non_stream()
    except Exception as exc:  # noqa: BLE001
        print(f"[non-stream] FAILED: {exc}", file=sys.stderr)
        ok_non_stream = False
    try:
        ok_stream = await smoke_stream()
    except Exception as exc:  # noqa: BLE001
        print(f"[stream] FAILED: {exc}", file=sys.stderr)
        ok_stream = False
    if ok_non_stream and ok_stream:
        print("SMOKE PASS：端点支持原生工具调用（非流式 + 流式）")
        return 0
    print("SMOKE INCONCLUSIVE：端点未发起工具调用或拒绝 tools 字段——"
          "若为 400 降级路径，agent 会自动无工具运行（行为可接受）；"
          "若模型只是没选择调用，可加强提问措辞后重试。")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
