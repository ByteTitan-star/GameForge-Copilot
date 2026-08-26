"""Godot codegen 单元测试。"""

from __future__ import annotations

import json

from app.forge.native.codegen import (
    READY_SIGNAL,
    materialize_godot_project,
    parse_godot_code_output,
)


def _valid_main_gd() -> str:
    return f'''extends Node2D

func _ready() -> void:
\tprint("{READY_SIGNAL}")
'''


def test_parse_godot_code_output_accepts_valid_json() -> None:
    raw = json.dumps(
        {
            "format": "godot-project",
            "files": {"scenes/main.gd": _valid_main_gd()},
        }
    )
    parsed = parse_godot_code_output(raw)
    assert not parsed.errors
    assert "scenes/main.gd" in parsed.files


def test_parse_godot_code_output_rejects_missing_ready_signal() -> None:
    raw = json.dumps(
        {
            "format": "godot-project",
            "files": {"scenes/main.gd": "extends Node2D\n"},
        }
    )
    parsed = parse_godot_code_output(raw)
    assert parsed.errors
    assert any(READY_SIGNAL in err for err in parsed.errors)


def test_materialize_godot_project_includes_template_files() -> None:
    files = materialize_godot_project({"scenes/main.gd": _valid_main_gd()})
    assert "project.godot" in files
    assert "scenes/main.tscn" in files
    assert READY_SIGNAL in files["scenes/main.gd"]
