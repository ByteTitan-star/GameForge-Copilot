"""CodeQaLoop：code ↔ playtest ↔ diagnose 有界子图。

【3 小时上手 · CodeQaLoop 阅读顺序（严格按序）】
────────────────────────────────────────
第 0 步(20min)  docs/superpowers/specs/2026-08-15-code-qa-loop-design.md
                ← 先建立「B 档硬门禁 / attempt=3 / 禁止静态冒充 QA」心智模型
第 1 步(15min)  【本文件】subgraphs/code_qa_loop.py
                ← 只看拓扑与 after_* 条件边，先别钻实现
第 2 步(20min)  graph.py → 搜 code_qa_loop_node
                ← 主图如何注入三节点、qa_ok 后 promote、exhausted 后 HITL
第 3 步(40min)  code_qa_exec.py → 三个 execute_*
                ← 真正干活：生成/试玩/诊断返回哪些 state 字段
第 4 步(25min)  sandbox/playtest.py → PlaytestResult / run_playtest*
                ← B 档验收：ok 不变量、infra vs product、永久 infra
第 5 步(15min)  code_candidate.py + reliability/artifact_gate.py
                ← candidate 与 current_version 分离；previewable≠publishable
第 6 步(15min)  qa/diagnose.py + llm_continuation.py
                ← 诊断 JSON；截断如何触发子图 retry
第 7 步(15min)  reliability/policy.py（code_or_repair/playtest/diagnose/code_qa_loop）
                ← 超时数字；外墙 = attempts × 三节点之和
第 8 步(选读)   build/integration.py / native/code_qa.py
                ← Vite 构建内环；Godot 平行管线（时间不够可跳过）

本文件职责：只编排边；节点禁止写 run.status / 禁止调 _fail。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.forge.llm_continuation import is_output_truncated_error
from app.sandbox.playtest import is_permanent_infra_error

NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class CodeQaLoopState(TypedDict, total=False):
    """子图状态：字段多与 ForgeState 同名；子图 ainvoke 期间独立流转，结束再写回主图。"""

    # ── 从主图注入的输入 ─────────────────────────────────────────
    design_doc: dict[str, Any] | str  # 已确认策划稿
    art_options: dict[str, Any]  # 美术选项（子图内较少直接用）
    art_direction: dict[str, Any]  # 选定美术方向（写入代码 prompt）
    artifacts: list[dict[str, str]]  # 素材列表
    entry_requirement: str | None  # 小改入口的用户需求（可直奔 code）

    # ── 循环控制（after_* 条件边主要看这些）──────────────────────
    attempt: int  # 当前第几次 code/QA（含首次；达上限 → exhausted）
    qa_ok: bool  # 试玩通过；主图据此决定是否 promote
    exhausted: bool  # 预算耗尽；主图据此进 qa_failed / sandbox_failed
    candidate_version: int | None  # 本轮候选版本号
    candidate_ready: bool  # True → after_code_or_repair 走 playtest
    candidate_kind: str | None  # single-html / project 等
    playtest_errors: list[str]  # 失败错误；截断时也塞在这里触发 retry
    console_logs: list[str]  # 控制台日志（diagnose 用）
    failure_kind: str | None  # product|build|infra|truncated… 决定下一条边
    qa_diagnosis: str  # diagnose 产出，下一轮 repair 注入
    motion_signal: str | None  # 试玩「在动」信号（通过时必有）
    code_qa_reset: bool  # 主图要求重置 attempt（HITL 重进时）

    # ── 提前结束（任一为真 → 条件边 __end__，交给主图）──────────
    paused: bool
    failed: bool
    hitl_stop: bool


def _max_attempts() -> int:
    """CodeQaLoop 总 attempt 上限（配置项 code_qa_max_attempts）。"""
    return int(settings.code_qa_max_attempts)


def after_code_or_repair(
    state: CodeQaLoopState,
) -> Literal["playtest", "diagnose", "retry", "exhausted", "__end__"]:
    """code_or_repair 之后的路由。

    优先级：暂停/失败 → 有候选去试玩 → 次数耗尽 → 输出截断再生成 → 其它失败去诊断。
    """
    if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
        return "__end__"
    if state.get("candidate_ready"):
        return "playtest"
    attempt = int(state.get("attempt") or 0)
    if attempt >= _max_attempts():
        return "exhausted"
    if is_output_truncated_error(list(state.get("playtest_errors") or [])):
        # LLM 输出被截断：不进 diagnose，直接再跑一轮 code（retry）
        return "retry"
    # build fail → diagnose（infra 不会从 code_or_repair 产生）
    return "diagnose"


def after_playtest(
    state: CodeQaLoopState,
) -> Literal["ok", "exhausted", "replay", "diagnose", "__end__"]:
    """playtest 之后的路由。

    - 通过 → mark_ok
    - infra 临时故障 → infra_replay（同 candidate 重放试玩）
    - infra 永久故障（缺 Playwright 等）→ 立刻 exhausted，避免空转
    - 产品/实现问题 → diagnose
    """
    if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
        return "__end__"
    if state.get("qa_ok"):
        return "ok"
    attempt = int(state.get("attempt") or 0)
    if attempt >= _max_attempts():
        return "exhausted"
    if state.get("failure_kind") == "infra":
        # Playwright/Chromium 缺失等环境问题：空转重试无意义，立即耗尽
        if is_permanent_infra_error(list(state.get("playtest_errors") or [])):
            return "exhausted"
        return "replay"
    return "diagnose"


def after_diagnose(
    state: CodeQaLoopState,
) -> Literal["code_or_repair", "__end__"]:
    """diagnose 写完诊断后，默认回到 code_or_repair 做 repair；暂停则结束子图。"""
    if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
        return "__end__"
    return "code_or_repair"


def build_code_qa_loop(
    *,
    code_or_repair: NodeFn,
    playtest: NodeFn,
    diagnose: NodeFn,
) -> Any:
    """编译 CodeQaLoop 子图。

    拓扑（简化）：
      START → code_or_repair ─┬─ candidate_ready → playtest ─┬─ qa_ok → mark_ok → END
                              ├─ truncated → 再 code_or_repair   ├─ infra 临时 → infra_replay
                              ├─ 其它失败 → diagnose ──────────┴─ product → diagnose
                              └─ attempt 耗尽 → mark_exhausted → END
                                         diagnose → code_or_repair

    三个业务节点由外部注入（主图绑定 code_qa_exec.execute_*）；
    节点禁止写 run.status / 调用 _fail。
    """

    async def infra_replay(state: CodeQaLoopState) -> dict[str, Any]:
        """infra：只加 attempt，保持同一 candidate，回到 playtest。"""
        return {
            "attempt": int(state.get("attempt") or 0) + 1,
            "qa_ok": False,
            "exhausted": False,
        }

    async def mark_ok(state: CodeQaLoopState) -> dict[str, Any]:
        """试玩通过：标记 qa_ok，供主图 after_code_qa 决定是否进 done。"""
        return {"qa_ok": True, "exhausted": False}

    async def mark_exhausted(state: CodeQaLoopState) -> dict[str, Any]:
        """预算耗尽：主图随后会 pause 到 qa_failed / sandbox_failed 等人介入。"""
        return {
            "qa_ok": False,
            "exhausted": True,
            "candidate_ready": False,
        }

    g = StateGraph(CodeQaLoopState)
    # 业务三节点（有外部 IO / LLM）
    g.add_node("code_or_repair", code_or_repair)  # type: ignore[call-overload]
    g.add_node("playtest", playtest)  # type: ignore[call-overload]
    g.add_node("diagnose", diagnose)  # type: ignore[call-overload]
    # 控制用轻量节点（只改状态字段）
    g.add_node("infra_replay", infra_replay)
    g.add_node("mark_ok", mark_ok)
    g.add_node("mark_exhausted", mark_exhausted)

    g.add_edge(START, "code_or_repair")
    g.add_conditional_edges(
        "code_or_repair",
        after_code_or_repair,
        {
            "playtest": "playtest",
            "diagnose": "diagnose",
            "retry": "code_or_repair",
            "exhausted": "mark_exhausted",
            END: END,
        },
    )
    g.add_conditional_edges(
        "playtest",
        after_playtest,
        {
            "ok": "mark_ok",
            "exhausted": "mark_exhausted",
            "replay": "infra_replay",
            "diagnose": "diagnose",
            END: END,
        },
    )
    g.add_edge("infra_replay", "playtest")
    g.add_conditional_edges(
        "diagnose",
        after_diagnose,
        {"code_or_repair": "code_or_repair", END: END},
    )
    g.add_edge("mark_ok", END)
    g.add_edge("mark_exhausted", END)
    return g.compile()
