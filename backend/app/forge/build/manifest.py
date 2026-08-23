"""Build Manifest Generator：平台侧生成 package.json / vite.config 等（§8）。"""

from __future__ import annotations

import fnmatch
import json
from typing import Any

from app.forge.build.catalog import BUILD_TOOL_PACKAGES, CATALOG_VERSION
from app.forge.build.constants import BUILDER_ALLOWED_BUILDS
from app.forge.build.profile import BuildProfile, default_build_profile
from app.forge.build.routing import BuildRouting, resolve_package_versions
from app.forge.build.template import load_vite_ts_template_files

# LLM source_files 不得覆盖的平台 manifest（ADR-07 P0-2）
PROTECTED_WORKSPACE_FILES = frozenset(
    {
        "package.json",
        "pnpm-workspace.yaml",
        "pnpm-lock.yaml",
        "package-lock.json",
        "yarn.lock",
        "tsconfig.json",
        "build-profile.json",
    }
)
PROTECTED_WORKSPACE_GLOBS = ("vite.config.*",)


def _normalize_workspace_rel(rel: str) -> str:
    """将工作区相对路径规范为 POSIX 风格（去 ./ 与反斜杠）。

    场景：is_protected_workspace_file 判断。
    参数：rel - 相对路径字符串。
    返回：规范化路径。
    """
    return rel.replace("\\", "/").lstrip("./")


def is_protected_workspace_file(rel: str) -> bool:
    """判断 LLM 源码是否不得覆盖平台生成的 manifest 文件。

    场景：merge_workspace 过滤 source_files。
    参数：rel - 工作区内相对路径。
    返回：受保护时为 True。
    """
    name = _normalize_workspace_rel(rel)
    if name in PROTECTED_WORKSPACE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in PROTECTED_WORKSPACE_GLOBS)


def _split_deps(resolved: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """将依赖字典拆分为 runtime dependencies 与 devDependencies。

    场景：generate_package_json。
    参数：resolved - 包名到版本映射。
    返回：(runtime, dev) 两个字典。
    """
    runtime: dict[str, str] = {}
    dev: dict[str, str] = {}
    for name, version in sorted(resolved.items()):
        if name in BUILD_TOOL_PACKAGES:
            dev[name] = version
        else:
            runtime[name] = version
    return runtime, dev


def generate_package_json(routing: BuildRouting) -> str:
    """根据 BuildRouting 生成 package.json 文本。

    场景：generate_manifest_files / Vite 工作区初始化。
    参数：routing - 工程形态路由。
    返回：带换行结尾的 JSON 字符串。
    """
    resolved = resolve_package_versions(routing)
    runtime, dev = _split_deps(resolved)
    payload: dict[str, Any] = {
        "name": "gameforge-project",
        "version": "0.0.0",
        "private": True,
        "type": "module",
        "scripts": {"build": "vite build"},
        "dependencies": runtime,
        "devDependencies": dev,
        "packageManager": "pnpm@11.21.0",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def generate_vite_config(routing: BuildRouting) -> str:
    """生成 vite.config.ts 内容（React 或默认 TS 模板）。

    场景：generate_manifest_files。
    参数：routing - 含 ui 字段的 BuildRouting。
    返回：Vite 配置 TypeScript 源码。
    """
    if routing.ui == "react":
        return (
            "import { defineConfig } from 'vite'\n"
            "import react from '@vitejs/plugin-react'\n\n"
            "export default defineConfig({\n"
            "  base: './',\n"
            "  plugins: [react()],\n"
            "  build: { outDir: 'dist', sourcemap: false },\n"
            "})\n"
        )
    return load_vite_ts_template_files()["vite.config.ts"] + "\n"


def _loads_json_object(raw: str) -> dict[str, Any]:
    """解析带 // 行注释的 JSON 文件（如模板 tsconfig.json）。"""
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        msg = "JSON 对象格式无效"
        raise ValueError(msg)
    parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        msg = "JSON 根节点必须是对象"
        raise TypeError(msg)
    return parsed


def generate_tsconfig(routing: BuildRouting) -> str:
    """基于模板生成 tsconfig.json，React 时注入 jsx 配置。

    场景：generate_manifest_files。
    参数：routing - 工程形态（影响 jsx）。
    返回：JSON 字符串。
    """
    base = _loads_json_object(load_vite_ts_template_files()["tsconfig.json"])
    if routing.ui == "react":
        opts = base.setdefault("compilerOptions", {})
        opts["jsx"] = "react-jsx"
    return json.dumps(base, ensure_ascii=False, indent=2) + "\n"


def generate_pnpm_workspace() -> str:
    """生成 pnpm-workspace.yaml（含 allowBuilds 硬约束）。

    场景：Vite 流水线工作区初始化。
    参数：无。
    返回：YAML 文本。
    """
    lines = [
        "# pnpm-workspace.yaml（平台生成，硬约束④）",
        "allowBuilds:",
    ]
    for pkg, allowed in sorted(BUILDER_ALLOWED_BUILDS.items()):
        lines.append(f"  {pkg}: {str(allowed).lower()}")
    return "\n".join(lines) + "\n"


def generate_build_profile(profile: BuildProfile | None = None) -> str:
    """生成 build-profile.json（builder/catalog/template 版本对齐）。

    场景：构建快照与可复现性审计。
    参数：profile - 可选自定义 BuildProfile。
    返回：JSON 字符串。
    """
    prof = profile or default_build_profile()
    # catalog 版本与 profile 对齐
    prof = BuildProfile(
        builder_version=prof.builder_version,
        dependency_catalog_version=CATALOG_VERSION,
        template_version=prof.template_version,
    )
    return prof.to_json() + "\n"


def generate_platform_index_html() -> str:
    """返回平台默认 index.html 模板内容。

    场景：merge_workspace 在 LLM 未提供入口页时注入。
    参数：无。
    返回：HTML 字符串。
    """
    return load_vite_ts_template_files()["index.html"]


def generate_manifest_files(
    routing: BuildRouting,
    profile: BuildProfile | None = None,
) -> dict[str, str]:
    """返回 build snapshot 文件（不含 lockfile，由 DependencyPreparer 生成）。"""
    return {
        "package.json": generate_package_json(routing),
        "vite.config.ts": generate_vite_config(routing),
        "tsconfig.json": generate_tsconfig(routing),
        "pnpm-workspace.yaml": generate_pnpm_workspace(),
        "build-profile.json": generate_build_profile(profile),
    }


def merge_workspace(
    routing: BuildRouting,
    source_files: dict[str, str],
    profile: BuildProfile | None = None,
) -> dict[str, str]:
    """平台 manifest + LLM 业务源码；缺 index.html 时平台注入。"""
    workspace = dict(generate_manifest_files(routing, profile))
    for rel, content in source_files.items():
        if is_protected_workspace_file(rel):
            continue
        workspace[rel] = content
    if "index.html" not in workspace:
        workspace["index.html"] = generate_platform_index_html()
    return workspace
