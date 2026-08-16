"""沙箱工厂：`sandbox_backend=local|docker|e2b`（P3；e2b 仅 PoC）。"""

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.sandbox.base import (
    BuildResult,
    OneShotSandboxAdapter,
    Sandbox,
    SandboxBackend,
    SandboxSession,
)
from app.sandbox.lifecycle import destroy_for_hitl, restore_after_hitl
from app.sandbox.local import LocalSandbox

_backend: SandboxBackend | None = None
_sandbox: Sandbox | None = None


def get_sandbox_backend() -> SandboxBackend:
    global _backend
    if _backend is None:
        from app.forge.tracing import observe_subsystem

        with observe_subsystem(
            "sandbox", "select_backend", metadata={"backend": settings.sandbox_backend}
        ):
            _backend = _build_backend(settings.sandbox_backend)
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
    from app.sandbox.e2b import clear_e2b_live_for_tests

    clear_e2b_live_for_tests()


def _build_backend(name: str) -> SandboxBackend:
    key = (name or "local").strip().lower()
    if key == "local":
        return LocalSandbox()
    if key == "docker":
        from app.sandbox.docker import DockerSandbox

        return DockerSandbox()
    if key == "e2b":
        from app.sandbox.e2b import E2BSandbox

        return E2BSandbox()
    raise AppError(
        ErrorCode.VALIDATION_ERROR,
        f"Unknown sandbox_backend={name!r}; expected local|docker|e2b",
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
]
