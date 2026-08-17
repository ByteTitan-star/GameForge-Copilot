"""沙箱工厂：`sandbox_backend=local|docker|daytona`。

默认偏好 Daytona；无 API key、无 SDK 或未启用时回退 docker→local。
"""

import importlib.util
import logging

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.sandbox.base import (
    BuildResult,
    OneShotSandboxAdapter,
    Sandbox,
    SandboxBackend,
    SandboxSession,
)
from app.sandbox.lifecycle import (
    destroy_for_hitl,
    restore_after_hitl,
    restore_sandbox_from_checkpoint,
    tier_from_hitl_meta,
)
from app.sandbox.local import LocalSandbox

log = logging.getLogger(__name__)

_backend: SandboxBackend | None = None
_sandbox: Sandbox | None = None


def get_sandbox_backend() -> SandboxBackend:
    global _backend
    if _backend is None:
        from app.forge.tracing import observe_subsystem

        chosen = _resolve_backend_name(settings.sandbox_backend)
        with observe_subsystem("sandbox", "select_backend", metadata={"backend": chosen}):
            _backend = _build_backend(chosen)
    return _backend


def get_sandbox() -> Sandbox:
    """遗留一次性接口（create→execute→destroy）。"""
    global _sandbox
    if _sandbox is None:
        _sandbox = OneShotSandboxAdapter(get_sandbox_backend())
    return _sandbox


def reset_sandbox_for_tests() -> None:
    """测试用：清空单例，下次按当前 settings 重建。"""
    global _backend, _sandbox
    _backend = None
    _sandbox = None
    from app.sandbox.daytona import clear_daytona_live_for_tests

    clear_daytona_live_for_tests()


def _daytona_sdk_available() -> bool:
    return importlib.util.find_spec("daytona") is not None


def _resolve_backend_name(name: str) -> str:
    key = (name or "local").strip().lower()
    if key != "daytona":
        return key
    if not settings.sandbox_daytona_enabled:
        return "docker"
    if not (settings.daytona_api_key or "").strip():
        return "docker"
    if not _daytona_sdk_available():
        log.warning(
            "daytona SDK not installed; falling back to docker sandbox "
            "(install: uv sync --extra daytona)"
        )
        return "docker"
    return "daytona"


def _build_backend(name: str) -> SandboxBackend:
    key = (name or "local").strip().lower()
    if key == "local":
        return LocalSandbox()
    if key == "docker":
        from app.sandbox.docker import DockerSandbox

        try:
            return DockerSandbox()
        except Exception:  # noqa: BLE001 — docker 客户端不可用时回退 local
            return LocalSandbox()
    if key == "daytona":
        from app.sandbox.daytona import DaytonaSandbox

        return DaytonaSandbox()
    raise AppError(
        ErrorCode.VALIDATION_ERROR,
        f"Unknown sandbox_backend={name!r}; expected local|docker|daytona",
    )


__all__ = [
    "BuildResult",
    "OneShotSandboxAdapter",
    "Sandbox",
    "SandboxBackend",
    "SandboxSession",
    "destroy_for_hitl",
    "get_sandbox",
    "get_sandbox_backend",
    "reset_sandbox_for_tests",
    "restore_after_hitl",
    "restore_sandbox_from_checkpoint",
    "tier_from_hitl_meta",
]
