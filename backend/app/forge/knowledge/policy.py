"""Node Retrieval Policy（ADR-14 §3.8；R0 确定性配置，无 LLM Router）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeRetrievalPolicy:
    domains: tuple[str, ...]
    categories: tuple[str, ...]


# plan 节点同时覆盖首次策划与 revise（graph 均用 node=plan）
_NODE_POLICIES: dict[str, NodeRetrievalPolicy] = {
    "plan": NodeRetrievalPolicy(
        domains=("design", "example"),
        categories=(
            "gameplay_mechanic",
            "game_genre",
            "design_principle",
            "gameplay_case",
        ),
    ),
    "revise": NodeRetrievalPolicy(
        domains=("design", "example"),
        categories=(
            "gameplay_mechanic",
            "design_principle",
            "gameplay_case",
        ),
    ),
    "art": NodeRetrievalPolicy(
        domains=("art", "example"),
        categories=("art_direction", "ui_case"),
    ),
    "art_detail": NodeRetrievalPolicy(
        domains=("art", "example"),
        categories=("art_direction", "ui_case"),
    ),
    "code": NodeRetrievalPolicy(
        domains=("platform",),
        categories=("engine_constraint", "output_contract"),
    ),
    "repair": NodeRetrievalPolicy(
        domains=("platform",),
        categories=("coding_rule", "engine_constraint"),
    ),
}


def policy_for_node(node: str) -> NodeRetrievalPolicy | None:
    return _NODE_POLICIES.get(node)
