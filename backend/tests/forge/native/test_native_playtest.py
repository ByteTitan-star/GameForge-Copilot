"""Native playtest bridge tests."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.native.godot.template_loader import materialize_godot_template
from app.forge.native.playtest import (
    run_native_playtest,
    should_run_native_playtest,
)


@pytest.mark.asyncio
async def test_should_run_when_godot_project_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "native_engine_enabled", True)
    ws = materialize_godot_template(tmp_path / "godot")
    assert should_run_native_playtest("godot4", ws) is True
    assert should_run_native_playtest("canvas", ws) is False


@pytest.mark.asyncio
async def test_run_native_playtest_without_godot_bin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "native_engine_enabled", True)
    monkeypatch.setattr(settings, "native_engine_godot_bin", "")
    ws = materialize_godot_template(tmp_path / "godot")
    result = await run_native_playtest("godot4", ws)
    assert result.ok is False
    assert result.playtest_mode == "godot_native"
    assert result.structured is not None
    assert result.failure_kind == "build"
