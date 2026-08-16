"""E2B Sandbox 真 SDK 适配（ADR-03：默认禁用，≠ 生产批准）。

依赖可选 extra ``e2b``（``uv sync --extra e2b``）。未安装 SDK 或未开 flag 时拒绝 create。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult, SandboxSession

log = logging.getLogger(__name__)

_WORKDIR = "/home/user/gameforge"
# 进程内持有活会话；HITL destroy 必须 kill 并弹出
_LIVE: dict[str, Any] = {}


class E2BSandbox:
    """AsyncSandbox 生命周期：create → execute → destroy。"""

    backend_id = "e2b"

    async def create(self, *, tier: str | None = None) -> SandboxSession:
        self._require_enabled()
        AsyncSandbox = _import_async_sandbox()
        kwargs: dict[str, Any] = {
            "timeout": settings.e2b_timeout_s,
            "allow_internet_access": settings.e2b_allow_internet,
        }
        if settings.e2b_api_key:
            kwargs["api_key"] = settings.e2b_api_key
        try:
            sbx = await AsyncSandbox.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 SDK/网络错误映射为沙箱失败
            raise AppError(ErrorCode.SANDBOX_FAILED, f"E2B create failed: {exc}") from exc
        sandbox_id = getattr(sbx, "sandbox_id", None) or getattr(sbx, "id", None) or ""
        session = SandboxSession.new(
            self.backend_id,
            tier=tier or settings.sandbox_default_tier,
            handle=str(sandbox_id),
        )
        _LIVE[session.id] = sbx
        return session

    async def execute(
        self,
        session: SandboxSession,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        if session.closed:
            return BuildResult(ok=False, error="sandbox session closed")
        sbx = await self._resolve_live(session)
        try:
            await sbx.commands.run(f"mkdir -p {_WORKDIR}", timeout=30)
            for rel, content in source.items():
                remote = f"{_WORKDIR}/{rel.lstrip('/')}"
                parent = remote.rsplit("/", 1)[0]
                if parent and parent != _WORKDIR:
                    await sbx.commands.run(f"mkdir -p {parent}", timeout=30)
                await sbx.files.write(remote, content)
            logs = ""
            if build_cmd:
                cmd = " && ".join(build_cmd)
                result = await sbx.commands.run(
                    f"cd {_WORKDIR} && {cmd}",
                    timeout=float(settings.e2b_timeout_s),
                )
                logs = (getattr(result, "stdout", "") or "") + (
                    getattr(result, "stderr", "") or ""
                )
                exit_code = int(getattr(result, "exit_code", 1) or 0)
                if exit_code != 0:
                    SANDBOX_RUNS.labels("e2b", "fail").inc()
                    return BuildResult(
                        ok=False, logs=logs, error=f"build exit {exit_code}"
                    )
            files = await self._collect(sbx, collect_root=collect_root)
            SANDBOX_RUNS.labels("e2b", "ok").inc()
            return BuildResult(ok=True, files=files, logs=logs)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            SANDBOX_RUNS.labels("e2b", "error").inc()
            return BuildResult(ok=False, error=str(exc))

    async def destroy(self, session: SandboxSession) -> None:
        if session.closed:
            return
        sbx = _LIVE.pop(session.id, None)
        if sbx is not None:
            try:
                kill = getattr(sbx, "kill", None)
                if kill is not None:
                    await kill()
            except Exception:  # noqa: BLE001 destroy 路径不得抛崩
                log.exception("e2b kill failed session=%s", session.id)
        session.closed = True
        session.handle = None

    async def _resolve_live(self, session: SandboxSession) -> Any:
        sbx = _LIVE.get(session.id)
        if sbx is not None:
            return sbx
        if not session.handle:
            raise AppError(ErrorCode.SANDBOX_FAILED, "E2B session handle missing")
        AsyncSandbox = _import_async_sandbox()
        connect = getattr(AsyncSandbox, "connect", None)
        if connect is None:
            raise AppError(
                ErrorCode.SANDBOX_FAILED,
                "E2B session lost and SDK has no connect(); recreate after HITL",
            )
        kwargs: dict[str, Any] = {}
        if settings.e2b_api_key:
            kwargs["api_key"] = settings.e2b_api_key
        try:
            sbx = await connect(session.handle, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                ErrorCode.SANDBOX_FAILED, f"E2B reconnect failed: {exc}"
            ) from exc
        _LIVE[session.id] = sbx
        return sbx

    async def _collect(self, sbx: Any, *, collect_root: str) -> dict[str, bytes]:
        root = _WORKDIR if collect_root in (".", "") else f"{_WORKDIR}/{collect_root}"
        files: dict[str, bytes] = {}
        listed = await sbx.commands.run(f"find {root} -type f", timeout=60)
        stdout = getattr(listed, "stdout", "") or ""
        limit = settings.artifact_max_size_mb * 1024 * 1024
        total = 0
        for line in stdout.splitlines():
            path = line.strip()
            if not path:
                continue
            data = await sbx.files.read(path, format="bytes")
            raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
            total += len(raw)
            if total > limit:
                raise AppError(ErrorCode.QUOTA_EXCEEDED, "产物超出大小上限")
            rel = path[len(root) :].lstrip("/")
            files[rel or path.rsplit("/", 1)[-1]] = raw
        return files

    def _require_enabled(self) -> None:
        if not settings.sandbox_e2b_enabled:
            raise AppError(
                ErrorCode.SANDBOX_FAILED,
                "E2B sandbox is PoC-only and disabled by default (ADR-03). "
                "Set sandbox_e2b_enabled=true only for approved benchmarks.",
            )


def _import_async_sandbox() -> Any:
    try:
        from e2b import AsyncSandbox  # type: ignore[import-not-found]
    except ImportError as exc:
        raise AppError(
            ErrorCode.SANDBOX_FAILED,
            "E2B SDK not installed; run: uv sync --extra e2b",
        ) from exc
    return AsyncSandbox


def clear_e2b_live_for_tests() -> None:
    _LIVE.clear()
