"""Worker 启动时清扫孤儿容器与临时目录（ADR-11）。"""

from __future__ import annotations

import contextlib
import logging
import shutil
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_CONTAINER_PREFIXES = ("gf-sandbox-", "gf-builder-")
_TEMP_PREFIXES = ("gf-docker-sandbox-", "gf-local-sandbox-", "gf-builder-")


async def cleanup_orphan_sandbox_resources() -> dict[str, int]:
    """Best-effort：删命名前缀孤儿容器 + tempfile 下匹配前缀目录。"""
    containers = await _cleanup_orphan_containers()
    dirs = _cleanup_temp_dirs()
    return {"containers": containers, "dirs": dirs}


async def _cleanup_orphan_containers() -> int:
    try:
        import aiodocker
    except ImportError:
        return 0
    removed = 0
    try:
        docker = aiodocker.Docker()
    except Exception:  # noqa: BLE001
        return 0
    try:
        containers = await docker.containers.list(all=True)
        for c in containers:
            name = ""
            try:
                info = await c.show()
                names = info.get("Name") or info.get("Names") or ""
                name = str(names[0] if names else "") if isinstance(names, list) else str(names)
                name = name.lstrip("/")
                if not any(name.startswith(p) for p in _CONTAINER_PREFIXES):
                    continue
                await c.delete(force=True)
                removed += 1
            except Exception:  # noqa: BLE001
                log.debug("orphan container cleanup skip name=%s", name, exc_info=True)
    except Exception:  # noqa: BLE001
        log.warning("orphan container list failed", exc_info=True)
    finally:
        with contextlib.suppress(Exception):
            await docker.close()
    return removed


def _cleanup_temp_dirs() -> int:
    root = Path(tempfile.gettempdir())
    removed = 0
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if not any(child.name.startswith(p) for p in _TEMP_PREFIXES):
                continue
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    except OSError:
        log.warning("temp dir cleanup failed", exc_info=True)
    return removed
