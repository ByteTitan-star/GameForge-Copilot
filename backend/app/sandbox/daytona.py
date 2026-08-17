"""Daytona Sandbox 适配（ADR-03：首选云沙箱）。

依赖可选 extra ``daytona``（``uv sync --extra daytona``）。未安装 SDK 或未开 flag 时拒绝 create。

进程内 ``_LIVE`` 仅作热缓存；远端 sandbox id 同时登记到 Redis，供 worker 启动对账回收
（ADR-11 §7），避免进程崩溃后远端沙箱泄漏计费。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult, SandboxSession

log = logging.getLogger(__name__)

_WORKDIR = "/tmp/gameforge"  # nosec B108 — Daytona sandbox workdir
# 进程内持有活会话；HITL destroy 必须 delete 并弹出
_LIVE: dict[str, dict[str, Any]] = {}
_REDIS_HANDLES_KEY = "gf:daytona:live_handles"


class DaytonaSandbox:
    """AsyncDaytona 生命周期：create → execute → destroy。"""

    backend_id = "daytona"

    async def create(self, *, tier: str | None = None) -> SandboxSession:
        self._require_enabled()
        daytona = self._new_client()
        try:
            sbx = await daytona.create(timeout=float(settings.daytona_timeout_s))
        except Exception as exc:  # noqa: BLE001 SDK/网络错误映射为沙箱失败
            raise AppError(ErrorCode.SANDBOX_FAILED, f"Daytona create failed: {exc}") from exc
        sandbox_id = str(getattr(sbx, "id", None) or getattr(sbx, "sandbox_id", "") or "")
        session = SandboxSession.new(
            self.backend_id,
            tier=tier or settings.sandbox_default_tier,
            handle=sandbox_id,
        )
        _LIVE[session.id] = {"client": daytona, "sandbox": sbx}
        await _register_remote_handle(sandbox_id)
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
            await sbx.fs.create_folder(_WORKDIR, "755")
            for rel, content in source.items():
                remote = f"{_WORKDIR}/{rel.lstrip('/')}"
                parent = remote.rsplit("/", 1)[0]
                if parent and parent != _WORKDIR:
                    await sbx.fs.create_folder(parent, "755")
                raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
                await sbx.fs.upload_file(raw, remote)
            logs = ""
            if build_cmd:
                cmd = " && ".join(build_cmd)
                result = await sbx.process.exec(
                    f"cd {_WORKDIR} && {cmd}",
                    timeout=float(settings.daytona_timeout_s),
                )
                logs = str(getattr(result, "result", "") or "")
                exit_code = int(getattr(result, "exit_code", 1) or 0)
                if exit_code != 0:
                    SANDBOX_RUNS.labels("daytona", "fail").inc()
                    return BuildResult(ok=False, logs=logs, error=f"build exit {exit_code}")
            files = await self._collect(sbx, collect_root=collect_root)
            SANDBOX_RUNS.labels("daytona", "ok").inc()
            return BuildResult(ok=True, files=files, logs=logs)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            SANDBOX_RUNS.labels("daytona", "error").inc()
            return BuildResult(ok=False, error=str(exc))

    async def destroy(self, session: SandboxSession) -> None:
        if session.closed:
            return
        entry = _LIVE.pop(session.id, None)
        handle = str(session.handle or "").strip()
        try:
            await _delete_remote(entry=entry, handle=handle)
        except Exception:  # noqa: BLE001 destroy 路径不得抛崩
            log.exception("daytona delete failed session=%s handle=%s", session.id, handle)
        if handle:
            await _unregister_remote_handle(handle)
        session.closed = True
        session.handle = None

    async def _resolve_live(self, session: SandboxSession) -> Any:
        entry = _LIVE.get(session.id)
        if entry is not None and entry.get("sandbox") is not None:
            return entry["sandbox"]
        if not session.handle:
            raise AppError(ErrorCode.SANDBOX_FAILED, "Daytona session handle missing")
        daytona = self._new_client()
        try:
            sbx = await daytona.get(session.handle)
        except Exception as exc:  # noqa: BLE001
            raise AppError(ErrorCode.SANDBOX_FAILED, f"Daytona reconnect failed: {exc}") from exc
        _LIVE[session.id] = {"client": daytona, "sandbox": sbx}
        await _register_remote_handle(str(session.handle))
        return sbx

    async def _collect(self, sbx: Any, *, collect_root: str) -> dict[str, bytes]:
        root = _WORKDIR if collect_root in (".", "") else f"{_WORKDIR}/{collect_root}"
        files: dict[str, bytes] = {}
        listed = await sbx.process.exec(f"find {root} -type f", timeout=60)
        stdout = str(getattr(listed, "result", "") or "")
        limit = settings.artifact_max_size_mb * 1024 * 1024
        total = 0
        for line in stdout.splitlines():
            path = line.strip()
            if not path:
                continue
            data = await sbx.fs.download_file(path)
            raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
            total += len(raw)
            if total > limit:
                raise AppError(ErrorCode.QUOTA_EXCEEDED, "产物超出大小上限")
            rel = path[len(root) :].lstrip("/")
            files[rel or path.rsplit("/", 1)[-1]] = raw
        return files

    def _require_enabled(self) -> None:
        if not settings.sandbox_daytona_enabled:
            raise AppError(
                ErrorCode.SANDBOX_FAILED,
                "Daytona sandbox disabled (ADR-03). "
                "Set sandbox_daytona_enabled=true with DAYTONA_API_KEY.",
            )
        if not (settings.daytona_api_key or "").strip():
            raise AppError(
                ErrorCode.SANDBOX_FAILED,
                "DAYTONA_API_KEY is required for sandbox_backend=daytona",
            )

    def _new_client(self) -> Any:
        AsyncDaytona, DaytonaConfig = _import_daytona()
        return AsyncDaytona(DaytonaConfig(api_key=settings.daytona_api_key.strip()))


def _import_daytona() -> tuple[Any, Any]:
    try:
        from daytona import AsyncDaytona, DaytonaConfig
    except ImportError as exc:
        raise AppError(
            ErrorCode.SANDBOX_FAILED,
            "Daytona SDK not installed; run: uv sync --extra daytona",
        ) from exc
    return AsyncDaytona, DaytonaConfig


def clear_daytona_live_for_tests() -> None:
    _LIVE.clear()


async def reconcile_daytona_orphans() -> int:
    """删除 Redis 登记但本进程 ``_LIVE`` 已不持有的远端 sandbox（worker 启动对账）。"""
    if not settings.sandbox_daytona_enabled or not (settings.daytona_api_key or "").strip():
        return 0
    handles = await _listed_remote_handles()
    if not handles:
        return 0
    live_remote_ids = {
        str(getattr(entry.get("sandbox"), "id", "") or "")
        for entry in _LIVE.values()
        if entry.get("sandbox") is not None
    }
    removed = 0
    for handle in handles:
        if not handle or handle in live_remote_ids:
            continue
        try:
            await _delete_remote(entry=None, handle=handle)
            await _unregister_remote_handle(handle)
            removed += 1
        except Exception:  # noqa: BLE001 best-effort
            log.warning("daytona orphan reconcile skip handle=%s", handle, exc_info=True)
            await _unregister_remote_handle(handle)
    return removed


async def _delete_remote(*, entry: dict[str, Any] | None, handle: str) -> None:
    client = entry.get("client") if entry else None
    sbx = entry.get("sandbox") if entry else None
    if client is not None and sbx is not None:
        await client.delete(sbx)
        return
    if not handle:
        return
    client = DaytonaSandbox()._new_client()
    sbx = await client.get(handle)
    await client.delete(sbx)


async def _register_remote_handle(handle: str) -> None:
    handle = (handle or "").strip()
    if not handle:
        return
    try:
        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await r.sadd(_REDIS_HANDLES_KEY, handle)
        finally:
            await r.aclose()
    except Exception:  # noqa: BLE001 Redis 不可用不阻断沙箱主路径
        log.debug("daytona register handle failed handle=%s", handle, exc_info=True)


async def _unregister_remote_handle(handle: str) -> None:
    handle = (handle or "").strip()
    if not handle:
        return
    try:
        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await r.srem(_REDIS_HANDLES_KEY, handle)
        finally:
            await r.aclose()
    except Exception:  # noqa: BLE001
        log.debug("daytona unregister handle failed handle=%s", handle, exc_info=True)


async def _listed_remote_handles() -> set[str]:
    try:
        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            members = await r.smembers(_REDIS_HANDLES_KEY)
        finally:
            await r.aclose()
    except Exception:  # noqa: BLE001
        log.debug("daytona list handles failed", exc_info=True)
        return set()
    return {str(m).strip() for m in (members or set()) if str(m).strip()}
