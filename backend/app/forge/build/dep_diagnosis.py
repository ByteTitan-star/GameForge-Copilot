"""构建日志依赖诊断（#161 方案 A）：module-not-found 类报错 → 结构化 JSON 修复提示。

只读日志、只产提示：不改变白名单校验、不自动安装任何包（ADR-07 不变）。
背景：LLM 代码 import 了某个包但未在 dependencies 声明时，离线构建报的
Cannot find module / Could not resolve 埋在原始 stderr 里，修复模型需要
自己猜该做什么；这里把结论显式拼成 JSON 软提示告诉它怎么改。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.forge.build.catalog import DEPENDENCY_CATALOG

# 各构建环节的"模块未解析"报错行；捕获组 = import 说明符
_UNRESOLVED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"Cannot find module '([^']+)'",
        r'Cannot find module "([^"]+)"',
        r"Could not resolve '([^']+)'",
        r'Could not resolve "([^"]+)"',
        r'Failed to resolve import "([^"]+)"',
        r"Failed to resolve import '([^']+)'",
    )
)

_MAX_FINDINGS = 6


def _package_of(spec: str) -> str:
    """import 说明符 → npm 包名：'@scope/pkg/sub'→'@scope/pkg'；相对/绝对路径返回空。"""
    text = (spec or "").strip()
    if not text or text.startswith(".") or text.startswith("/"):
        return ""
    parts = text.split("/")
    if text.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def diagnose_dependency_failure(logs: str) -> list[dict[str, Any]]:
    """扫描构建日志，为每个未解析的包 import 产出一条结构化诊断。

    同一包只报一次；最多 _MAX_FINDINGS 条，避免日志洪水撑爆修复提示词。
    """
    findings: dict[str, dict[str, Any]] = {}
    for line in (logs or "").splitlines():
        spec = next(
            (m.group(1) for p in _UNRESOLVED_PATTERNS if (m := p.search(line))),
            None,
        )
        if spec is None:
            continue
        pkg = _package_of(spec)
        if not pkg or pkg in findings:
            continue
        if pkg in DEPENDENCY_CATALOG:
            action = (
                f"add '{pkg}' to the dependencies field of the project JSON "
                "(it is in the platform catalog; keep the import as-is)"
            )
        else:
            action = (
                f"'{pkg}' is NOT in the platform catalog and cannot be installed; "
                "rewrite the code to remove this import and use a catalog package "
                "instead, or inline the functionality without the dependency"
            )
        findings[pkg] = {
            "kind": "undeclared_or_unresolved_dependency",
            "package": pkg,
            "in_catalog": pkg in DEPENDENCY_CATALOG,
            "action": action,
            "evidence": line.strip()[:200],
        }
        if len(findings) >= _MAX_FINDINGS:
            break
    return list(findings.values())


def dependency_hint_block(logs: str) -> str:
    """诊断结果 → 修复提示词里的 JSON 软提示块；无命中返回空串（保留原始日志即可）。"""
    items = diagnose_dependency_failure(logs)
    if not items:
        return ""
    body = json.dumps(items, ensure_ascii=False, indent=2)
    return "【依赖诊断（结构化提示：按 action 字段修正，原始日志附后）】\n" + body


def enrich_build_error(logs: str) -> str:
    """原始构建日志 → 带结构化诊断前缀的日志；用于修复模型与耗尽路径的输入。"""
    hint = dependency_hint_block(logs)
    if not hint:
        return logs
    return f"{hint}\n\n{logs}"
