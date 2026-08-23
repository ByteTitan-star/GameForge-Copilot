"""Hosting backend 工厂（B6）。"""

from __future__ import annotations

from app.core.config import settings
from app.hosting import local as local_backend

_backend = None


def get_hosting_backend():
    """按 settings.hosting_backend 返回单例 Hosting 后端。

    场景：store 模块委托读写产物。
    返回：local 模块或 S3HostingBackend 实例。
    """
    global _backend
    if _backend is not None:
        return _backend
    if settings.hosting_backend == "s3":
        from app.hosting.s3 import S3HostingBackend

        _backend = S3HostingBackend()
    else:
        _backend = local_backend
    return _backend


def reset_hosting_for_tests() -> None:
    """重置 Hosting 后端单例。

    场景：pytest teardown 切换 local/s3 配置。
    """
    global _backend
    _backend = None
