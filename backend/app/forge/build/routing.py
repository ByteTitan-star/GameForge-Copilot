"""工程形态 Routing Schema（docs/build-pipeline §5）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.forge.build.catalog import DEPENDENCY_CATALOG, validate_catalog_packages
from app.forge.engine_router import SUPPORTED_ENGINES, normalize_engine_id

BuildKind = Literal["none", "vite"]
UiKind = Literal["none", "react"]

_RENDERER_PACKAGES: dict[str, str] = {
    "phaser3": "phaser",
    "pixijs": "pixi.js",
}

_UI_PACKAGES: dict[str, tuple[str, ...]] = {
    "react": ("react", "react-dom"),
}


@dataclass(frozen=True)
class BuildRouting:
    build: BuildKind = "none"
    renderer: str = "canvas"
    ui: UiKind = "none"
    dependencies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "build": self.build,
            "renderer": self.renderer,
            "ui": self.ui,
            "dependencies": list(self.dependencies),
        }


def _as_build(value: object) -> BuildKind:
    if value == "vite":
        return "vite"
    return "none"


def _as_ui(value: object) -> UiKind:
    if value == "react":
        return "react"
    return "none"


def _as_deps(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return tuple(out)


def coerce_build_routing(raw: Any, *, engine_id: str = "canvas") -> BuildRouting:
    """从 design_doc.build_routing 或 LLM project JSON 归一化。"""
    renderer = normalize_engine_id(engine_id)
    if not isinstance(raw, dict):
        return BuildRouting(renderer=renderer)
    renderer = normalize_engine_id(raw.get("renderer", renderer))
    return BuildRouting(
        build=_as_build(raw.get("build")),
        renderer=renderer,
        ui=_as_ui(raw.get("ui")),
        dependencies=_as_deps(raw.get("dependencies")),
    )


def routing_from_design_doc(design_doc: dict[str, Any]) -> BuildRouting:
    engine_id = design_doc.get("engine", {}).get("id", "canvas")
    raw = design_doc.get("build_routing")
    routing = coerce_build_routing(raw, engine_id=engine_id)
    if routing.renderer == "canvas" and isinstance(raw, dict) and not raw.get("renderer"):
        return BuildRouting(
            build=routing.build,
            renderer=normalize_engine_id(engine_id),
            ui=routing.ui,
            dependencies=routing.dependencies,
        )
    return routing


def resolve_package_versions(routing: BuildRouting) -> dict[str, str]:
    """平台补齐 renderer/ui 基础依赖 + Agent 额外依赖，返回 {包名: 固定版本}。"""
    names: list[str] = list(routing.dependencies)
    renderer_pkg = _RENDERER_PACKAGES.get(routing.renderer)
    if renderer_pkg:
        names.append(renderer_pkg)
    if routing.ui in _UI_PACKAGES:
        names.extend(_UI_PACKAGES[routing.ui])
    # 构建工具
    names.extend(["typescript", "vite"])
    if routing.ui == "react":
        names.append("@vitejs/plugin-react")

    resolved: dict[str, str] = {}
    for name in names:
        version = DEPENDENCY_CATALOG.get(name)
        if version:
            resolved[name] = version
    return resolved


def validate_routing(routing: BuildRouting) -> list[str]:
    errors: list[str] = []
    if routing.build not in ("none", "vite"):
        errors.append(f"build 必须是 none 或 vite，当前: {routing.build}")
    if routing.renderer not in SUPPORTED_ENGINES:
        errors.append(f"renderer 不受支持: {routing.renderer}")
    if routing.ui not in ("none", "react"):
        errors.append(f"ui 必须是 none 或 react，当前: {routing.ui}")
    unknown = validate_catalog_packages(list(routing.dependencies))
    if unknown:
        errors.append(f"dependencies 含未授权包: {', '.join(unknown)}")
    return errors


def should_use_vite_pipeline(routing: BuildRouting, *, enabled: bool) -> bool:
    return enabled and routing.build == "vite"
