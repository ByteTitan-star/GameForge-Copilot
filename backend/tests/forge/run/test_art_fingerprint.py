"""P6：Art dependency fingerprint — NFC、canonical JSON、版本门控复用。"""

from __future__ import annotations

from app.forge.art_fingerprint import (
    FINGERPRINT_VERSION,
    art_dependency_fingerprint,
    can_reuse_art,
    canonical_dumps,
)


def test_unicode_nfc_equivalent_text_same_fingerprint() -> None:
    composed = {"presentation": {"visual_style": "café像素"}}
    decomposed = {"presentation": {"visual_style": "cafe\u0301像素"}}
    fp1, ver1 = art_dependency_fingerprint(composed)
    fp2, ver2 = art_dependency_fingerprint(decomposed)
    assert ver1 == ver2 == FINGERPRINT_VERSION
    assert fp1 == fp2


def test_json_key_order_does_not_change_fingerprint() -> None:
    a = canonical_dumps({"b": 1, "a": {"z": True, "y": None}})
    b = canonical_dumps({"a": {"y": None, "z": True}, "b": 1})
    assert a == b
    doc_a = {"presentation": {"color_palette": ["#111"], "visual_style": "flat"}}
    doc_b = {"presentation": {"visual_style": "flat", "color_palette": ["#111"]}}
    assert art_dependency_fingerprint(doc_a) == art_dependency_fingerprint(doc_b)


def test_ordered_array_order_changes_fingerprint() -> None:
    first = {"ui": {"screens": ["menu", "playing", "victory"]}}
    swapped = {"ui": {"screens": ["victory", "playing", "menu"]}}
    assert art_dependency_fingerprint(first)[0] != art_dependency_fingerprint(swapped)[0]


def test_different_fingerprint_version_cannot_reuse_art() -> None:
    fp, ver = art_dependency_fingerprint({"presentation": {"visual_style": "flat"}})
    assert can_reuse_art(stored_fp=fp, stored_version=ver, new_fp=fp, new_version=ver)
    assert not can_reuse_art(
        stored_fp=fp,
        stored_version=ver,
        new_fp=fp,
        new_version="art-dependency-fingerprint-v2",
    )
    assert not can_reuse_art(stored_fp=fp, stored_version=ver, new_fp="deadbeef", new_version=ver)
    assert not can_reuse_art(stored_fp=None, stored_version=ver, new_fp=fp, new_version=ver)
