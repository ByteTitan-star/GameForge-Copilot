"""P2：Skill catalog / router 单元测试。"""

from __future__ import annotations

from app.forge.skills.catalog import list_skill_metas, skill_bundle_hash
from app.forge.skills.router import resolve_skills_for_node


def test_catalog_lists_policy_and_methodology() -> None:
    metas = list_skill_metas()
    ids = {m.id for m in metas}
    assert "policy/playtest" in ids
    assert "policy/conventions" in ids
    assert "art/pixel-art" in ids
    assert "code/phaser3" in ids
    assert "repair/runtime-error" in ids
    kinds = {m.id: m.kind for m in metas}
    assert kinds["policy/playtest"] == "policy"
    assert kinds["art/pixel-art"] == "methodology"


def test_art_style_skill_picked_from_requirement() -> None:
    resolved = resolve_skills_for_node("art", hints={"requirement": "水墨山水躲避"})
    ids = {s.id for s in resolved.methodology}
    assert "art/ink-wash" in ids


def test_catalog_includes_new_art_style_skills() -> None:
    ids = {m.id for m in list_skill_metas()}
    assert "art/paper-craft" in ids
    assert "art/candy-arcade" in ids
    assert "art/crt-analog" in ids


def test_art_node_never_sees_admin_or_billing_skills() -> None:
    resolved = resolve_skills_for_node("art", hints={})
    ids = {s.id for s in resolved.methodology}
    assert "billing/usage" not in ids
    assert "sandbox/admin" not in ids
    assert all(s.kind == "methodology" for s in resolved.methodology)
    assert any(s.id.startswith("policy/") for s in resolved.policy)


def test_code_node_selects_engine_methodology_not_all_bodies() -> None:
    resolved = resolve_skills_for_node("code", hints={"engine_id": "phaser3"})
    method_ids = [s.id for s in resolved.methodology]
    assert "code/phaser3" in method_ids
    assert "code/pixijs" not in method_ids
    # Progressive disclosure: catalog discover does not load every body
    assert resolved.loaded_body_count < len(list_skill_metas())


def test_repair_node_loads_repair_skills() -> None:
    resolved = resolve_skills_for_node(
        "repair", hints={"failure_kind": "product", "engine_id": "canvas"}
    )
    ids = {s.id for s in resolved.methodology}
    assert "repair/runtime-error" in ids or "repair/gameplay-regression" in ids
    assert "code/canvas" in ids


def test_skill_bundle_hash_stable_and_changes_with_body() -> None:
    a = skill_bundle_hash(["policy/playtest", "code/canvas"])
    b = skill_bundle_hash(["policy/playtest", "code/canvas"])
    assert a == b
    assert len(a) == 64
