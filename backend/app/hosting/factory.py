"""Hosting backend 工厂（B6）。"""

from __future__ import annotations

from app.core.config import settings
from app.hosting import local as local_backend

_backend = None


def get_hosting_backend():
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
    global _backend
    _backend = None
