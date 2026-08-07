"""沙箱工厂：`sandbox_backend=local|docker`（docs/09）。"""

from app.core.config import settings
from app.sandbox.base import BuildResult, Sandbox
from app.sandbox.local import LocalSandbox

_sandbox: Sandbox | None = None


def get_sandbox() -> Sandbox:
    global _sandbox
    if _sandbox is None:
        if settings.sandbox_backend == "docker":
            from app.sandbox.docker import DockerSandbox

            _sandbox = DockerSandbox()
        else:
            _sandbox = LocalSandbox()
    return _sandbox


def reset_sandbox_for_tests() -> None:
    """测试用：清空单例，下次按当前 settings 重建。"""
    global _sandbox
    _sandbox = None


__all__ = ["BuildResult", "Sandbox", "get_sandbox", "reset_sandbox_for_tests"]
