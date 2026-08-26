"""Godot Docker exec helper tests."""

from __future__ import annotations

from pathlib import Path

from app.forge.native.godot.docker_exec import build_docker_godot_cmd


def test_build_docker_godot_cmd_mounts_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    cmd = build_docker_godot_cmd(
        ws,
        image="gameforge-godot-builder:v1",
        godot_args=["--headless", "--path", str(ws), "--import"],
    )
    assert cmd[0:3] == ["docker", "run", "--rm"]
    assert f"{ws.resolve()}:/workspace" in cmd
    assert "gameforge-godot-builder:v1" in cmd
    assert cmd[-1] == "--import"
    assert "/workspace" in cmd
