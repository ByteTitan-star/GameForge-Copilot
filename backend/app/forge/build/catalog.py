"""Dependency Catalog：平台控制的 npm 包 allowlist（docs/build-pipeline §7）。"""

from __future__ import annotations

# 固定精确版本；LLM 不得使用 latest/*/^
DEPENDENCY_CATALOG: dict[str, str] = {
    "phaser": "3.80.1",
    "pixi.js": "7.4.0",
    "react": "19.1.1",
    "react-dom": "19.1.1",
    "matter-js": "0.20.0",
    "howler": "2.2.4",
    "gsap": "3.13.0",
    "typescript": "5.9.2",
    "vite": "7.1.3",
    "@vitejs/plugin-react": "5.0.2",
}

# 构建工具链 devDependencies，不进运行时 dependencies
BUILD_TOOL_PACKAGES: frozenset[str] = frozenset({"typescript", "vite", "@vitejs/plugin-react"})

CATALOG_VERSION = "2026-08-14.1"


def catalog_version_for(package: str) -> str | None:
    """查询 catalog 中某 npm 包的钉死版本号。

    场景：manifest 生成、依赖解析、校验 LLM 声明的 dependencies。
    参数：package — npm 包名。
    返回：固定版本字符串；未收录时 None。
    """
    return DEPENDENCY_CATALOG.get(package)


def validate_catalog_packages(names: list[str]) -> list[str]:
    """返回不在 catalog 内的包名列表。

    场景：routing 校验、project 输出门禁，拦截未授权 npm 依赖。
    参数：names — 待检查的包名列表。
    返回：不在 allowlist 内的包名（已 strip、忽略空串）。
    """
    unknown: list[str] = []
    for name in names:
        pkg = name.strip()
        if pkg and pkg not in DEPENDENCY_CATALOG:
            unknown.append(pkg)
    return unknown
