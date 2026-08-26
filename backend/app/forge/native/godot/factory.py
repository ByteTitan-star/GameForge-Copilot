"""Godot adapter factory（ADR-13）。"""

from __future__ import annotations

from app.core.config import settings
from app.forge.native.godot.adapter import GodotAdapter
from app.forge.native.godot.template_loader import godot_template_root


def create_godot_adapter() -> GodotAdapter:
    return GodotAdapter(
        godot_version=settings.native_engine_godot_version,
        template_root=godot_template_root(),
    )
