"""E2B Sandbox PoC（ADR-03 Pending：默认禁用，不得作为国内生产默认后端）。

集成成功 ≠ 生产批准。未显式开启 ``sandbox_e2b_enabled`` 时拒绝 create。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.sandbox.base import BuildResult, SandboxSession


class E2BSandbox:
    """PoC 占位：生命周期接口齐备，默认拒绝以免误开源码出境路径。"""

    backend_id = "e2b"

    async def create(self, *, tier: str | None = None) -> SandboxSession:
        if not settings.sandbox_e2b_enabled:
            raise AppError(
                ErrorCode.SANDBOX_FAILED,
                "E2B sandbox is PoC-only and disabled by default (ADR-03). "
                "Set sandbox_e2b_enabled=true only for approved benchmarks.",
            )
        raise AppError(
            ErrorCode.SANDBOX_FAILED,
            "E2B adapter is not implemented yet; DockerSandbox remains the production baseline.",
        )

    async def execute(
        self,
        session: SandboxSession,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        raise AppError(ErrorCode.SANDBOX_FAILED, "E2B execute is unavailable")

    async def destroy(self, session: SandboxSession) -> None:
        session.closed = True
        session.handle = None
