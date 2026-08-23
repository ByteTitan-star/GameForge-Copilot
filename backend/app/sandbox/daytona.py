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
        """在 Daytona 云端创建沙箱会话并登记 Redis 句柄。

        场景：Forge 构建需云沙箱隔离时。
        参数：tier - 资源档位，缺省用 sandbox_default_tier。
        返回：含远端 sandbox id 的 SandboxSession。
        """
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
        """上传源码、可选执行构建命令并采集产物。

        场景：DaytonaSandbox 执行构建流水线。
        参数：session、source 文件映射、build_cmd、collect_root。
        返回：BuildResult（含 files/logs 或 error）。
        """
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
        """销毁远端 sandbox 并清理进程内缓存与 Redis 登记。

        场景：HITL 暂停、构建结束或会话超时。
        参数：session - 待销毁会话。
        """
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
        """从进程内缓存或远端 handle 恢复可用 sandbox 对象。

        场景：execute 前确保 sbx 可调用。
        参数：session - 含 handle 的会话。
        返回：Daytona SDK sandbox 实例。
        """
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
        """递归下载远端工作区文件并校验总大小上限。

        场景：execute 构建成功后采集产物。
        参数：sbx - sandbox 实例；collect_root - 相对工作区子目录。
        返回：相对路径 → 文件字节的 dict。
        """
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
        """校验 Daytona feature flag 与 API Key 已配置。

        场景：create 前门禁。
        返回：未启用或缺密钥时抛 AppError。
        """
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
        """构造 AsyncDaytona 客户端（使用配置中的 API Key）。

        场景：create、_resolve_live、_delete_remote。
        返回：AsyncDaytona 实例。
        """
        AsyncDaytona, DaytonaConfig = _import_daytona()
        return AsyncDaytona(DaytonaConfig(api_key=settings.daytona_api_key.strip()))


def _import_daytona() -> tuple[Any, Any]:
    """延迟导入 Daytona SDK，未安装时映射为 SANDBOX_FAILED。

    场景：_new_client 首次调用。
    返回：(AsyncDaytona, DaytonaConfig) 类元组。
    """
    try:
        from daytona import AsyncDaytona, DaytonaConfig
    except ImportError as exc:
        raise AppError(
            ErrorCode.SANDBOX_FAILED,
            "Daytona SDK not installed; run: uv sync --extra daytona",
        ) from exc
    return AsyncDaytona, DaytonaConfig


def clear_daytona_live_for_tests() -> None:
    """清空进程内 _LIVE 缓存（pytest 隔离）。

    场景：测试 teardown 避免会话泄漏。
    """
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
    """删除远端 Daytona sandbox（优先复用已有 client/sbx）。

    场景：destroy、orphan reconcile。
    参数：entry - 进程内缓存项；handle - 远端 sandbox id。
    """
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
    """将远端 sandbox id 登记到 Redis 集合（worker 对账用）。

    场景：create、_resolve_live 成功后。
    参数：handle - 远端 sandbox id。
    """
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
    """从 Redis 集合移除远端 sandbox id。

    场景：destroy 成功或 orphan 清理后。
    参数：handle - 远端 sandbox id。
    """
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
    """读取 Redis 中登记的全部远端 sandbox id。

    场景：reconcile_daytona_orphans 启动对账。
    返回：handle 字符串集合；Redis 不可用返回空集。
    """
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
