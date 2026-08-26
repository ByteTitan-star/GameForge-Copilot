"""Godot P0 模板物化（ADR-13 §3.4 template-first）。"""

from __future__ import annotations

import shutil
from pathlib import Path

_TEMPLATE_REL = Path(__file__).resolve().parent / "template"


def godot_template_root() -> Path:
    return _TEMPLATE_REL


def materialize_godot_template(workspace: Path) -> Path:
    """将固定模板复制到 workspace；返回 workspace 根目录。"""
    workspace.mkdir(parents=True, exist_ok=True)
    root = godot_template_root()
    if not root.is_dir():
        msg = f"godot template missing: {root}"
        raise FileNotFoundError(msg)
    for item in root.rglob("*"):
        rel = item.relative_to(root)
        dest = workspace / rel
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
    return workspace
