"""节点执行策略：统一 timeout / retry 预算（与 CodeQa/Build 预算正交）。"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.types import RetryPolicy, TimeoutPolicy

from app.core.config import settings
from app.core.errors import AppError


@dataclass(frozen=True, slots=True)
class NodeExecutionPolicy:
    """单节点执行策略。

    run_timeout_margin_s：相对 llm_request_timeout 的额外裕量；
    若 fixed_run_timeout_s 非空则使用固定墙钟（无 LLM 节点）。
    """

    max_attempts: int = 2
    run_timeout_margin_s: float = 60.0
    fixed_run_timeout_s: float | None = None
    idle_timeout_s: float | None = None


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
    """计算 LangGraph 节点墙钟超时秒数。

    场景：langgraph_timeout_policy。
    参数：node - 图节点名。
    返回：run_timeout 秒（含 LLM 与 build 预算）。
    """
    policy = NODE_EXECUTION_POLICIES[node]
    if policy.fixed_run_timeout_s is not None:
        return float(policy.fixed_run_timeout_s)
    llm = float(settings.llm_request_timeout)
    if node == "code_qa_loop":
        attempts = max(1, int(settings.code_qa_max_attempts))
        per = (
            resolve_node_run_timeout("code_or_repair")
            + resolve_node_run_timeout("playtest")
            + resolve_node_run_timeout("diagnose")
        )
        return float(attempts * per)
    if node == "code_or_repair" and settings.build_pipeline_enabled:
        build_budget = float(
            max(1, settings.build_max_retries) * max(1, settings.builder_timeout_s)
        )
        return llm + float(policy.run_timeout_margin_s) + build_budget
    return llm + float(policy.run_timeout_margin_s)


def langgraph_timeout_policy(node: str) -> TimeoutPolicy:
    """为节点生成 LangGraph TimeoutPolicy。

    场景：graph._build_graph 注册节点时。
    参数：node。
    返回：含 run_timeout 与可选 idle_timeout 的策略。
    """
    policy = NODE_EXECUTION_POLICIES[node]
    run_timeout = resolve_node_run_timeout(node)
    if policy.idle_timeout_s is not None:
        return TimeoutPolicy(
            run_timeout=run_timeout,
            idle_timeout=float(policy.idle_timeout_s),
        )
    return TimeoutPolicy(run_timeout=run_timeout)


def _default_retry_on(exc: Exception) -> bool:
    """LangGraph 节点重试谓词：业务终态错误不重试。

    场景：langgraph_retry_policy。
    参数：exc - 节点抛出的异常。
    返回：可重试时为 True。
    """
    if isinstance(exc, AppError):
        return False
    return type(exc).__name__ not in {"ContentAttacked", "RunFinalized"}


def langgraph_retry_policy(node: str) -> RetryPolicy:
    """为节点生成 LangGraph RetryPolicy（max_attempts + retry_on）。

    场景：graph._build_graph 注册节点时。
    参数：node。
    返回：RetryPolicy 实例。
    """
    policy = NODE_EXECUTION_POLICIES[node]
    return RetryPolicy(
        max_attempts=max(1, policy.max_attempts),
        retry_on=_default_retry_on,
    )
