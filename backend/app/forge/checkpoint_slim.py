"""Checkpoint 瘦身：有 revision 引用时不持久化大 payload；恢复时再 hydrate。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact_revision import ArtifactRevision

_PLAN_REV_KEY = "active_plan_revision_id"
_ART_REV_KEY = "active_art_revision_id"
_ART_OPTIONS_REV_KEY = "active_art_options_revision_id"


def slim_checkpoint_payloads(state: dict[str, Any]) -> dict[str, Any]:
    """有 revision id 时去掉对应大对象；无 id 时保留（兼容旧胖 checkpoint）。"""
    out = dict(state)
    if out.get(_PLAN_REV_KEY):
        out.pop("design_doc", None)
    if out.get(_ART_REV_KEY):
        out.pop("art_direction", None)
    if out.get(_ART_OPTIONS_REV_KEY):
        out.pop("art_options", None)
    return out


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


async def hydrate_checkpoint_payloads(db: AsyncSession, state: dict[str, Any]) -> dict[str, Any]:
    """从 ArtifactRevision 补回 design_doc / art_direction / art_options。"""
    out = dict(state)
    if not isinstance(out.get("design_doc"), dict):
        plan_id = _parse_uuid(out.get(_PLAN_REV_KEY))
        if plan_id is not None:
            row = await db.get(ArtifactRevision, plan_id)
            if row is not None and isinstance(row.payload, dict):
                out["design_doc"] = row.payload
    if not isinstance(out.get("art_direction"), dict):
        art_id = _parse_uuid(out.get(_ART_REV_KEY))
        if art_id is not None:
            row = await db.get(ArtifactRevision, art_id)
            if row is not None and isinstance(row.payload, dict):
                out["art_direction"] = row.payload
    if not isinstance(out.get("art_options"), dict):
        opts_id = _parse_uuid(out.get(_ART_OPTIONS_REV_KEY))
        if opts_id is not None:
            row = await db.get(ArtifactRevision, opts_id)
            if row is not None and isinstance(row.payload, dict):
                out["art_options"] = row.payload
    return out
