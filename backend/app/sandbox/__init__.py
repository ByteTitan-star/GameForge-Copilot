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
    """获取或创建全局 SandboxBackend 单例。

    场景：Forge 构建、QA 等需要沙箱后端的入口。
    返回：已按 settings 解析并实例化的 SandboxBackend。
    """
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
    """检测 daytona Python SDK 是否已安装。

    场景：解析 sandbox_backend=daytona 时决定能否启用云沙箱。
    返回：find_spec 成功为 True，否则 False。
    """
    return importlib.util.find_spec("daytona") is not None


def _resolve_backend_name(name: str) -> str:
    """将配置名解析为实际可用的后端标识。

    场景：get_sandbox_backend 选择实现前做 daytona 降级链。
    参数：name — settings.sandbox_backend 原始值。
    返回：local、docker 或 daytona（仅当 SDK 与 key 均可用）。
    """
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
    """按名称实例化具体沙箱后端。

    场景：单例首次初始化或测试 reset 后重建。
    参数：name — 已解析的后端名。
    返回：LocalSandbox、DockerSandbox 或 DaytonaSandbox 实例。
    """
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
