"""Godot template materialization and validate tests."""

from __future__ import annotations

import pytest

from app.forge.native.godot.adapter import GodotAdapter
from app.forge.native.godot.factory import create_godot_adapter
from app.forge.native.godot.template_loader import (
    godot_template_root,
    materialize_godot_template,
)


@pytest.mark.asyncio
async def test_materialize_template_and_validate(tmp_path) -> None:
    workspace = materialize_godot_template(tmp_path / "godot_proj")
    assert (workspace / "project.godot").is_file()
    assert (workspace / "scenes" / "main.tscn").is_file()

    adapter = GodotAdapter(
        godot_version="4.3",
        template_root=godot_template_root(),
    )
    diag = await adapter.validate_project(workspace)
    assert diag.ok is True
    assert diag.phase == "validate"


@pytest.mark.asyncio
async def test_validate_fails_without_main_scene(tmp_path) -> None:
    workspace = tmp_path / "empty"
    workspace.mkdir()
    (workspace / "project.godot").write_text(
        "config_version=5\n",
        encoding="utf-8",
    )
    adapter = create_godot_adapter()
    diag = await adapter.validate_project(workspace)
    assert diag.ok is False
    assert "main_scene" in diag.messages[0]
