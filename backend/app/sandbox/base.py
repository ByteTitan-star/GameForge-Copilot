"""沙箱抽象：P3 SandboxBackend 生命周期 + 兼容一次性 execute。

docs/2026-08-15-forge-runtime-evolution-plan.md P3：
create → execute → destroy；不强制 pause/snapshot。
Playwright 冒烟仍在 Worker 侧，不并入 Backend。
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class BuildResult:
    ok: bool
    files: dict[str, bytes] = field(default_factory=dict)
    logs: str = ""
    error: str | None = None


@dataclass
class SandboxSession:
    """一次可执行会话句柄；HITL 长等待默认 destroy，不保留计费长会话。"""

    id: str
    backend_id: str
    tier: str = "standard"
    closed: bool = False
    # backend-private workspace / remote id
    handle: str | None = None

    @staticmethod
    def new(
        backend_id: str, *, tier: str = "standard", handle: str | None = None
    ) -> SandboxSession:
        return SandboxSession(
            id=str(uuid.uuid4()),
            backend_id=backend_id,
            tier=tier,
            handle=handle,
        )


class SandboxBackend(Protocol):
    """可插拔沙箱后端（local / docker / e2b PoC）。"""

    async def create(self, *, tier: str | None = None) -> SandboxSession: ...

    async def execute(
        self,
        session: SandboxSession,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult: ...

    async def destroy(self, session: SandboxSession) -> None: ...


class Sandbox(Protocol):
    """遗留一次性接口：内部等价于 create → execute → destroy。"""

    async def execute(
        self,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult: ...


class OneShotSandboxAdapter:
    """把 SandboxBackend 适配为遗留 Sandbox.execute 一次性调用。"""

    def __init__(self, backend: SandboxBackend) -> None:
        self._backend = backend

    async def execute(
        self,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
        tier: str | None = None,
        hints: dict | None = None,
    ) -> BuildResult:
        from app.sandbox.tiers import record_sandbox_outcome, resolve_create_tier

        chosen = resolve_create_tier(source=source, hints=hints, explicit=tier)
        session = await self._backend.create(tier=chosen)
        try:
            result = await self._backend.execute(
                session, source, build_cmd, collect_root=collect_root
            )
            record_sandbox_outcome(
                tier=session.tier,
                ok=result.ok,
                error=result.error,
                backend=session.backend_id,
            )
            return result
        finally:
            await self._backend.destroy(session)
