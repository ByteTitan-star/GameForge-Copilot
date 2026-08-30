"""节点执行策略：统一 timeout / retry 预算（与 CodeQa/Build 预算正交）。

【本文件对 CodeQaLoop = 阅读顺序第 7 步 · 约 15min】
────────────────────────────────────────
只盯这 4 个 key：
  code_or_repair / playtest / diagnose  — 子图内单次墙钟
  code_qa_loop                          — 外墙 = attempts × 三节点之和（max_attempts=1）

完整 3 小时顺序见 subgraphs/code_qa_loop.py 文件头。
开关：settings.reliability_node_timeout=False 时 graph 不挂策略。
设计依据：docs/adr/ADR-09-timeout-and-io-boundaries.md
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.types import RetryPolicy, TimeoutPolicy

from app.core.config import settings
from app.core.errors import AppError


@dataclass(frozen=True, slots=True)
class NodeExecutionPolicy:
    """单节点执行策略。

    字段含义：
    - max_attempts: LangGraph RetryPolicy 最大尝试次数（含首次）
    - run_timeout_margin_s: 相对 llm_request_timeout 的额外裕量（秒）
    - fixed_run_timeout_s: 若非空则用固定墙钟，忽略 LLM 基线（适合无 LLM 节点）
    - idle_timeout_s: 可选；节点空闲超时（当前表里基本未用）
    """

    max_attempts: int = 2
    run_timeout_margin_s: float = 60.0
    fixed_run_timeout_s: float | None = None
    idle_timeout_s: float | None = None


# ── 策略表（key 是「预算类别」，不是主图节点名）──────────────────────────
# entry_router: 规则路由，几乎瞬时；策略预留，主图实际用 route_start 条件边
# plan / art:   主图策划、美术相关节点共用
# code_or_repair / playtest / diagnose: CodeQaLoop 子图内单次预算
# code_qa_loop: 子图整体外墙（attempts × 三节点之和），外墙本身不重试
# done:         收尾落库 / 发事件，短超时、不重试
NODE_EXECUTION_POLICIES: dict[str, NodeExecutionPolicy] = {
    "entry_router": NodeExecutionPolicy(fixed_run_timeout_s=10.0, max_attempts=1),
    "plan": NodeExecutionPolicy(run_timeout_margin_s=60.0, max_attempts=2),
    "art": NodeExecutionPolicy(run_timeout_margin_s=60.0, max_attempts=2),
    "code_or_repair": NodeExecutionPolicy(run_timeout_margin_s=120.0, max_attempts=2),
    "playtest": NodeExecutionPolicy(fixed_run_timeout_s=180.0, max_attempts=2),
    "diagnose": NodeExecutionPolicy(run_timeout_margin_s=30.0, max_attempts=2),
    "done": NodeExecutionPolicy(fixed_run_timeout_s=30.0, max_attempts=1),
    "code_qa_loop": NodeExecutionPolicy(
        fixed_run_timeout_s=None,
        run_timeout_margin_s=0.0,
        max_attempts=1,
    ),
}


def resolve_node_run_timeout(node: str) -> float:
    """解析某策略 key 的墙钟超时（秒）。

    优先级：
    1) fixed_run_timeout_s 直接用
    2) code_qa_loop → 动态外墙 = attempt 次数 × 三节点之和
    3) code_or_repair 且开启 build → llm + margin + build 链预算
    4) 默认 → llm + margin
    """
    policy = NODE_EXECUTION_POLICIES[node]
    if policy.fixed_run_timeout_s is not None:
        return float(policy.fixed_run_timeout_s)
    llm = float(settings.llm_request_timeout)
    if node == "code_qa_loop":
        # 外墙必须盖住「整段有界闭环」，否则子图内部还没耗尽就被节点超时掐死
        attempts = max(1, int(settings.code_qa_max_attempts))
        per = (
            resolve_node_run_timeout("code_or_repair")
            + resolve_node_run_timeout("playtest")
            + resolve_node_run_timeout("diagnose")
        )
        return float(attempts * per)
    if node == "code_or_repair" and settings.build_pipeline_enabled:
        # build 可能串行重试多次，节点预算要跟着 build_max_retries 放大（ADR-09 §4）
        build_budget = float(
            max(1, settings.build_max_retries) * max(1, settings.builder_timeout_s)
        )
        return llm + float(policy.run_timeout_margin_s) + build_budget
    return llm + float(policy.run_timeout_margin_s)


def langgraph_timeout_policy(node: str) -> TimeoutPolicy:
    """构造传给 StateGraph.add_node(..., timeout=...) 的 TimeoutPolicy。"""
    policy = NODE_EXECUTION_POLICIES[node]
    run_timeout = resolve_node_run_timeout(node)
    if policy.idle_timeout_s is not None:
        return TimeoutPolicy(
            run_timeout=run_timeout,
            idle_timeout=float(policy.idle_timeout_s),
        )
    return TimeoutPolicy(run_timeout=run_timeout)


def _default_retry_on(exc: Exception) -> bool:
    """哪些异常允许进入节点级重试（ADR-09 §5）。

    业务终态 / 再试无意义的异常必须排除，否则会把攻击流量或配置错误成倍放大：
    - AppError：业务错误
    - ContentAttacked：内容安全命中
    - RunFinalized：run 已终态，禁止再写
    """
    if isinstance(exc, AppError):
        return False
    return type(exc).__name__ not in {"ContentAttacked", "RunFinalized"}


def langgraph_retry_policy(node: str) -> RetryPolicy:
    """构造传给 StateGraph.add_node(..., retry_policy=...) 的 RetryPolicy。"""
    policy = NODE_EXECUTION_POLICIES[node]
    return RetryPolicy(
        max_attempts=max(1, policy.max_attempts),
        retry_on=_default_retry_on,
    )
