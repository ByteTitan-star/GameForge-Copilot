"""ChunkPlanner and policy registry tests (#146)."""

from __future__ import annotations

from app.forge.knowledge.chunk_planner import (
    assert_no_truncation,
    plan_markdown,
    plan_text,
)
from app.forge.knowledge.chunk_policy import (
    EMBED_MAX_TOKENS,
    effective_max_tokens,
    policy_for_category,
)
from app.forge.memory.context_builder import estimate_tokens


def test_policy_for_gameplay_mechanic() -> None:
    p = policy_for_category("gameplay_mechanic")
    assert p.name == "design_principle"
    assert effective_max_tokens(p) <= EMBED_MAX_TOKENS


def test_plan_markdown_splits_headings() -> None:
    md = """# Ignore H1

## 原则一

肉鸽塔防需要随机成长与构筑深度。

## 原则二

塔协同应形成明确 combo，而不是数值膨胀。
"""
    drafts = plan_markdown(md, category="design_principle")
    assert len(drafts) >= 2
    assert assert_no_truncation(drafts) == 0.0
    assert all(estimate_tokens(d.text) <= EMBED_MAX_TOKENS for d in drafts)


def test_plan_text_splits_oversized() -> None:
    policy = policy_for_category("design_principle")
    long = "塔防协同机制。" * 200
    assert estimate_tokens(long) > EMBED_MAX_TOKENS
    drafts = plan_text(long, policy=policy)
    assert len(drafts) > 1
    assert assert_no_truncation(drafts) == 0.0
