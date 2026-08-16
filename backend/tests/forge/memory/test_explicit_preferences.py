"""P1：Explicit 偏好抽取。"""

from __future__ import annotations

from app.forge.memory.explicit import (
    extract_explicit_preferences,
    looks_like_explicit_preference,
)


def test_without_marker_returns_empty() -> None:
    assert extract_explicit_preferences("这次做个跑酷") == []
    assert looks_like_explicit_preference("这次做个跑酷") is False


def test_extract_pixel_style_preference() -> None:
    prefs = extract_explicit_preferences("以后都用像素风")
    assert len(prefs) == 1
    assert prefs[0]["category"] == "visual"
    assert prefs[0]["key"] == "style"
    assert prefs[0]["value_json"]["style"] == "pixel"
    assert prefs[0]["source"] == "explicit"


def test_extract_generic_note_when_marker_only() -> None:
    prefs = extract_explicit_preferences("以后按我说的来")
    assert len(prefs) == 1
    assert prefs[0]["category"] == "general"
    assert prefs[0]["key"] == "note"
