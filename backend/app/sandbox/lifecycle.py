"""HITL 长等待：显式 destroy，resume 后 restore（新建 session，不强制 snapshot）。"""

from __future__ import annotations

from typing import Any

from app.sandbox.base import SandboxBackend, SandboxSession


async def destroy_for_hitl(
    backend: SandboxBackend, session: SandboxSession
) -> dict[str, Any]:
    """暂停前销毁沙箱会话，避免 HITL 期间计费/泄漏。

    返回可写入 checkpoint 的元数据（不含可执行 handle）。
    """
    meta = {
        "session_id": session.id,
        "backend_id": session.backend_id,
        "tier": session.tier,
        "destroyed_for_hitl": True,
    }
    await backend.destroy(session)
    return meta


async def restore_after_hitl(
    backend: SandboxBackend, *, tier: str | None = None
) -> SandboxSession:
    """HITL 恢复后新建沙箱会话（本仓库不强制跨等待 snapshot）。"""
    return await backend.create(tier=tier)


def sandbox_session_from_checkpoint(raw: dict[str, Any] | None) -> SandboxSession | None:
    """从 checkpoint 中的 sandbox_session 字段还原句柄（可能已 destroy）。"""
    if not isinstance(raw, dict):
        return None
    sid = raw.get("id") or raw.get("session_id")
    backend_id = raw.get("backend_id")
    if not sid or not backend_id:
        return None
    return SandboxSession(
        id=str(sid),
        backend_id=str(backend_id),
        tier=str(raw.get("tier") or "standard"),
        closed=bool(raw.get("closed", False)),
        handle=raw.get("handle"),
    )
