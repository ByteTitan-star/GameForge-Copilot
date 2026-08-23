"""策划稿 game_states 与验收探针共享的状态工具。"""

from __future__ import annotations

from typing import Any

from app.forge.design_doc import REQUIRED_STATE_IDS, coerce_design_doc

_PROBE_TERMINAL_IDS = frozenset({"paused", "game_over", "level_complete", "victory"})


def declared_state_ids(design_doc: dict[str, Any] | str | None) -> set[str]:
    if not design_doc:
        return set()
    doc = coerce_design_doc(design_doc)
    ids: set[str] = set()
    for state in doc.get("game_states") or []:
        if isinstance(state, dict):
            sid = str(state.get("id") or "").strip()
            if sid:
                ids.add(sid)
    return ids


def missing_required_state_ids(design_doc: dict[str, Any] | str | None) -> list[str]:
    declared = declared_state_ids(design_doc)
    if not declared:
        return []
    return sorted(REQUIRED_STATE_IDS - declared)


def cheat_probe_state_ids(design_doc: dict[str, Any] | str | None) -> list[str]:
    """有 __AG_CHEAT__ 时需可切换验证的终态/暂停态。"""
    targets = declared_state_ids(design_doc) & _PROBE_TERMINAL_IDS
    return sorted(targets)


def state_referenced_in_html(html: str, state_id: str) -> bool:
    token = state_id.strip().lower()
    if not token:
        return False
    text = (html or "").lower()
    patterns = (
        token,
        token.replace("_", ""),
        f"screen-{token}",
        f"'{token}'",
        f'"{token}"',
    )
    return any(p in text for p in patterns)


def required_state_source_errors(html: str, design_doc: dict[str, Any] | str | None) -> list[str]:
    errors: list[str] = []
    for sid in missing_required_state_ids(design_doc):
        errors.append(f"ACCEPTANCE: game_states 缺少必需状态 {sid!r}")
    for sid in declared_state_ids(design_doc):
        if not state_referenced_in_html(html, sid):
            errors.append(f"ACCEPTANCE: 产物未引用 game_states.{sid!r}")
    return errors
