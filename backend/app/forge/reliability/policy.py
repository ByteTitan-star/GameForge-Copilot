"""节点执行策略：统一 timeout / retry 预算（与 CodeQa/Build 预算正交）。"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.types import RetryPolicy, TimeoutPolicy

from app.core.config import settings


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
    "playtest": NodeExecutionPolicy(fixed_run_timeout_s=90.0, max_attempts=2),
    "diagnose": NodeExecutionPolicy(run_timeout_margin_s=30.0, max_attempts=2),
    # 外墙：给满 attempt 预算的粗上限；细粒度 timeout 在子图节点上
    "code_qa_loop": NodeExecutionPolicy(
        fixed_run_timeout_s=None,
        run_timeout_margin_s=0.0,
        max_attempts=1,
    ),
}


def resolve_node_run_timeout(node: str) -> float:
    policy = NODE_EXECUTION_POLICIES[node]
    if policy.fixed_run_timeout_s is not None:
        return float(policy.fixed_run_timeout_s)
    llm = float(settings.llm_request_timeout)
    if node == "code_qa_loop":
        # attempt × (code + playtest + diagnose) 粗算，避免外墙先于子步骤超时
        attempts = max(1, int(settings.code_qa_max_attempts))
        per = (
            resolve_node_run_timeout("code_or_repair")
            + resolve_node_run_timeout("playtest")
            + resolve_node_run_timeout("diagnose")
        )
        return float(attempts * per)
    return llm + float(policy.run_timeout_margin_s)


def langgraph_timeout_policy(node: str) -> TimeoutPolicy:
    policy = NODE_EXECUTION_POLICIES[node]
    kwargs: dict[str, float] = {"run_timeout": resolve_node_run_timeout(node)}
    if policy.idle_timeout_s is not None:
        kwargs["idle_timeout"] = float(policy.idle_timeout_s)
    return TimeoutPolicy(**kwargs)


def langgraph_retry_policy(node: str) -> RetryPolicy:
    policy = NODE_EXECUTION_POLICIES[node]
    return RetryPolicy(max_attempts=max(1, policy.max_attempts))
