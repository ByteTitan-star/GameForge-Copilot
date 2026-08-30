"""Chunk Policy Registry（ADR-14 §3.6.3；#146 MVP）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkPolicy:
    name: str
    max_tokens: int
    target_min: int
    target_max: int
    overlap_tokens: int
    categories: frozenset[str]


_POLICIES: dict[str, ChunkPolicy] = {
    "design_principle": ChunkPolicy(
        name="design_principle",
        max_tokens=400,
        target_min=120,
        target_max=280,
        overlap_tokens=0,
        categories=frozenset({"design_principle", "gameplay_mechanic"}),
    ),
    "gameplay_case": ChunkPolicy(
        name="gameplay_case",
        max_tokens=400,
        target_min=150,
        target_max=320,
        overlap_tokens=0,
        categories=frozenset({"gameplay_case", "game_genre", "historical_game"}),
    ),
    "art_direction": ChunkPolicy(
        name="art_direction",
        max_tokens=380,
        target_min=100,
        target_max=260,
        overlap_tokens=0,
        categories=frozenset({"art_direction", "ui_case", "ui_style"}),
    ),
    "platform_rule": ChunkPolicy(
        name="platform_rule",
        max_tokens=350,
        target_min=80,
        target_max=220,
        overlap_tokens=0,
        categories=frozenset({"engine_constraint", "coding_rule", "output_contract"}),
    ),
    "narrative_doc": ChunkPolicy(
        name="narrative_doc",
        max_tokens=450,
        target_min=200,
        target_max=380,
        overlap_tokens=40,
        categories=frozenset(),  # 长文 Markdown 默认
    ),
}

# Embed 硬上限（bge-small-zh 512 留余量）；与 policy.max 取更严者
EMBED_MAX_TOKENS = 480


def policy_by_name(name: str) -> ChunkPolicy | None:
    return _POLICIES.get(name.strip())


def policy_for_category(category: str) -> ChunkPolicy:
    cat = category.strip()
    for policy in _POLICIES.values():
        if cat in policy.categories:
            return policy
    return _POLICIES["narrative_doc"]


def effective_max_tokens(policy: ChunkPolicy) -> int:
    return min(policy.max_tokens, EMBED_MAX_TOKENS)
