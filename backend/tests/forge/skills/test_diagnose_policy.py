"""diagnose 节点应注入 playtest Policy。"""

from __future__ import annotations

from app.forge.skills.router import resolve_skills_for_node


def test_diagnose_receives_playtest_policy() -> None:
    resolved = resolve_skills_for_node(
        "diagnose",
        hints={"engine_id": "canvas", "failure_kind": "infra"},
    )
    policy_ids = [s.id for s in resolved.policy]
    assert "policy/playtest" in policy_ids
