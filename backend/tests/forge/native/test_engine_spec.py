"""ADR-13 Native EngineSpec 注册表。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.native.engine_spec import (
    EngineFamily,
    get_engine_spec,
    list_enabled_engines,
    native_engine_enabled,
)


def test_native_engine_disabled_by_default() -> None:
    assert native_engine_enabled() is False
    assert get_engine_spec("godot4") is None


def test_web_engines_always_listed() -> None:
    enabled = list_enabled_engines()
    ids = {spec.id for spec in enabled}
    assert "canvas" in ids
    assert "godot4" not in ids


def test_godot_listed_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "native_engine_enabled", True)
    spec = get_engine_spec("godot4")
    assert spec is not None
    assert spec.family is EngineFamily.NATIVE
    assert spec.adapter == "GodotAdapter"
