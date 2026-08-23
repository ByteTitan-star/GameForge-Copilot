"""Sandbox / builder 共享资源表（ADR-11：禁止 docker/local/builder 各写一套魔法数）。"""

from __future__ import annotations

import os
from typing import Any

TIER_LIMITS: dict[str, dict[str, Any]] = {
    "lite": {"mem_limit": "256m", "nano_cpus": 500_000_000, "timeout_s": 45},
    "standard": {"mem_limit": "512m", "nano_cpus": 1_000_000_000, "timeout_s": 60},
    "heavy": {"mem_limit": "1g", "nano_cpus": 2_000_000_000, "timeout_s": 120},
}


def tier_limits(tier: str | None) -> dict[str, Any]:
    """按档位返回内存、CPU、超时等资源限制。

    场景：Docker/Local sandbox 执行前查询 TIER_LIMITS。
    参数：tier - lite/standard/heavy，未知档位回退 standard。
    返回：含 mem_limit、nano_cpus、timeout_s 的 dict 副本。
    """
    key = (tier or "standard").strip().lower()
    return dict(TIER_LIMITS.get(key, TIER_LIMITS["standard"]))


def parse_mem_bytes(spec: str) -> int:
    """将 Docker 风格内存规格（如 512m、1g）解析为字节数。

    场景：Docker HostConfig.Memory 配置。
    参数：spec - 内存字符串。
    返回：字节整数。
    """
    s = spec.strip().lower()
    if s.endswith("g"):
        return int(float(s[:-1]) * 1024**3)
    if s.endswith("m"):
        return int(float(s[:-1]) * 1024**2)
    return int(s)


def docker_user_spec() -> str:
    """与宿主同 uid/gid，避免 bind mount 产物无法清理（CI runner ≠ node:1000）。"""
    if os.name == "nt":
        return "node"
    return f"{os.getuid()}:{os.getgid()}"  # type: ignore[attr-defined]


def docker_log_host_config() -> dict[str, Any]:
    """json-file 轮转（ADR-11）。

    不用 AutoRemove：容器退出后仍须读 log，AutoRemove 会竞态 404。
    """
    return {
        "AutoRemove": False,
        "LogConfig": {
            "Type": "json-file",
            "Config": {"max-size": "2m", "max-file": "2"},
        },
    }
