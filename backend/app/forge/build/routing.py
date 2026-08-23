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
        """序列化为 design_doc / checkpoint 可存的 dict。

        场景：持久化 build_routing。
        参数：无。
        返回：含 build/renderer/ui/dependencies 的字典。
        """
        return {
            "build": self.build,
            "renderer": self.renderer,
            "ui": self.ui,
            "dependencies": list(self.dependencies),
        }


def _as_build(value: object) -> BuildKind:
    """将任意输入规范为 BuildKind（仅 vite 或 none）。

    场景：coerce_build_routing。
    参数：value - 原始 build 字段。
    返回：\"vite\" 或 \"none\"。
    """
    if value == "vite":
        return "vite"
    return "none"


def _as_ui(value: object) -> UiKind:
    """将任意输入规范为 UiKind（仅 react 或 none）。

    场景：coerce_build_routing。
    参数：value - 原始 ui 字段。
    返回：\"react\" 或 \"none\"。
    """
    if value == "react":
        return "react"
    return "none"


def _as_deps(value: object) -> tuple[str, ...]:
    """将 dependencies 列表规范为非空包名元组。

    场景：coerce_build_routing。
    参数：value - 原始 dependencies（通常为 list）。
    返回：去重前的有序包名元组。
    """
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
    """从策划稿 design_doc 提取并归一化 BuildRouting。

    场景：Code 阶段选择 Vite 流水线或单文件 HTML。
    参数：design_doc - 含 engine 与 build_routing 的 dict。
    返回：BuildRouting 实例。
    """
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
    """校验 BuildRouting 字段合法性与依赖白名单。

    场景：写入 checkpoint 前门禁。
    参数：routing - 待校验路由。
    返回：错误文案列表（空表示通过）。
    """
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
    """判断是否走 Vite+TS 构建流水线。

    场景：code_or_repair_node 分支。
    参数：routing、enabled - 功能开关。
    返回：开关开启且 routing.build==vite 时为 True。
    """
    return enabled and routing.build == "vite"
