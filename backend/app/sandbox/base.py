"""沙箱抽象：P3 SandboxBackend 生命周期 + 兼容一次性 execute。

docs/2026-08-15-forge-runtime-evolution-plan.md P3：
create → execute → destroy；不强制 pause/snapshot。
Playwright 冒烟仍在 Worker 侧，不并入 Backend。
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass
class BuildResult:
    ok: bool
    files: dict[str, bytes] = field(default_factory=dict)
    logs: str = ""
    error: str | None = None
    # ADR-11：infra/build/timeout/oom；None 表示成功或未分类
    failure_kind: Literal["infra", "build", "timeout", "oom"] | None = None


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
        """工厂方法：生成带新 UUID 的会话句柄。

        场景：各后端 create 返回统一 SandboxSession。
        参数：backend_id — 后端标识；tier — 资源档位；handle — 后端私有工作区/远端 id。
        返回：未关闭的新 SandboxSession。
        """
        return SandboxSession(
            id=str(uuid.uuid4()),
            backend_id=backend_id,
            tier=tier,
            handle=handle,
        )


class SandboxBackend(Protocol):
    """可插拔沙箱后端（local / docker / daytona）。"""

    async def create(self, *, tier: str | None = None) -> SandboxSession:
        """创建可执行沙箱会话。

        场景：P3 生命周期 create → execute → destroy。
        参数：tier — 可选资源档位。
        返回：SandboxSession 句柄。
        """
        ...

    async def execute(
        self,
        session: SandboxSession,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        """在已有会话中写入源码并可选构建、采集产物。

        场景：单次构建流水线主路径。
        参数：session — 会话；source — 相对路径→内容；
        build_cmd — 构建命令；collect_root — 采集根目录。
        返回：BuildResult（含 files/logs/error）。
        """
        ...

    async def destroy(self, session: SandboxSession) -> None:
        """销毁会话并释放后端资源。

        场景：执行结束或 HITL 长等待前显式清理。
        参数：session — 待销毁会话。
        """
        ...


class Sandbox(Protocol):
    """遗留一次性接口：内部等价于 create → execute → destroy。"""

    async def execute(
        self,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
        tier: str | None = None,
        hints: dict | None = None,
    ) -> BuildResult:
        """遗留一次性接口：内部 create→execute→destroy。

        场景：旧调用方未迁移到 SandboxBackend 时。
        参数：source、build_cmd、collect_root、tier、hints。
        返回：BuildResult。
        """
        ...


class OneShotSandboxAdapter:
    """把 SandboxBackend 适配为遗留 Sandbox.execute 一次性调用。"""

    def __init__(self, backend: SandboxBackend) -> None:
        """绑定底层 SandboxBackend。

        场景：get_sandbox 构造遗留 Sandbox 适配器。
        参数：backend — 实际沙箱后端实例。
        """
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
        """解析 tier 后创建会话、执行构建并始终 destroy。

        场景：兼容旧 Sandbox.execute 调用并记录 tier telemetry。
        参数：source、build_cmd、collect_root、tier、hints。
        返回：BuildResult。
        """
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
