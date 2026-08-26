"""EngineSpec 注册表（Web + Native；ADR-13 §3.3）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config import settings
from app.forge.engine_router import SUPPORTED_ENGINES


class EngineFamily(StrEnum):
    WEB = "web"
    NATIVE = "native"


@dataclass(frozen=True)
class EngineSpec:
    id: str
    family: EngineFamily
    enabled: bool
    adapter: str


_WEB_SPECS: tuple[EngineSpec, ...] = tuple(
    EngineSpec(id=eid, family=EngineFamily.WEB, enabled=True, adapter="WebEngineAdapter")
    for eid in sorted(SUPPORTED_ENGINES)
)

_NATIVE_SPECS: tuple[EngineSpec, ...] = (
    EngineSpec(
        id="godot4",
        family=EngineFamily.NATIVE,
        enabled=True,
        adapter="GodotAdapter",
    ),
)

_SPECS: dict[str, EngineSpec] = {spec.id: spec for spec in (*_WEB_SPECS, *_NATIVE_SPECS)}


def native_engine_enabled() -> bool:
    return bool(settings.native_engine_enabled)


def _spec_enabled(spec: EngineSpec) -> bool:
    if spec.family is EngineFamily.NATIVE:
        return native_engine_enabled()
    return spec.enabled


def get_engine_spec(engine_id: str) -> EngineSpec | None:
    spec = _SPECS.get(engine_id)
    if spec is None:
        return None
    if not _spec_enabled(spec):
        return None
    return spec


def list_enabled_engines() -> list[EngineSpec]:
    return [spec for spec in _SPECS.values() if _spec_enabled(spec)]
