"""Godot P0 pipeline orchestration tests."""

from __future__ import annotations

import pytest

from app.forge.native.godot.adapter import GodotAdapter, GodotDiagnostics
from app.forge.native.godot.pipeline import run_godot_p0_loop
from app.forge.native.godot.template_loader import materialize_godot_template


@pytest.mark.asyncio
async def test_p0_loop_success_with_stubbed_phases(tmp_path, monkeypatch) -> None:
    workspace = materialize_godot_template(tmp_path / "proj")
    adapter = GodotAdapter(
        godot_version="4.3",
        template_root=workspace,
    )

    async def _ok_build(_ws) -> GodotDiagnostics:
        return GodotDiagnostics(phase="build", ok=True, messages=())

    async def _ok_run(_ws) -> GodotDiagnostics:
        return GodotDiagnostics(phase="run", ok=True, messages=(), logs_excerpt="GAMEFORGE_READY")

    monkeypatch.setattr(
        "app.forge.native.godot.pipeline.create_godot_adapter",
        lambda: adapter,
    )
    monkeypatch.setattr(adapter, "build", _ok_build)
    monkeypatch.setattr(adapter, "run_headless", _ok_run)

    result = await run_godot_p0_loop(workspace)
    assert result.ok is True
    assert result.phase == "run"


@pytest.mark.asyncio
async def test_p0_loop_stops_on_validate_failure(tmp_path) -> None:
    workspace = tmp_path / "bad"
    workspace.mkdir()
    result = await run_godot_p0_loop(workspace)
    assert result.ok is False
    assert result.phase == "validate"
