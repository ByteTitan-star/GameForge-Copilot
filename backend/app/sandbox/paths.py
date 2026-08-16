"""Workspace 相对路径纵深校验（ADR-11）。"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from app.core.errors import AppError, ErrorCode


def resolve_workspace_rel(workspace: Path, rel: str) -> Path:
    """规范化 rel 并确保落在 workspace 内；否则抛 SANDBOX_FAILED。"""
    base = workspace.resolve()
    path = PurePosixPath(str(rel).replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise AppError(ErrorCode.SANDBOX_FAILED, "非法工作区路径")
    target = (base / Path(*path.parts)).resolve()
    try:
        target.relative_to(base)
    except ValueError as e:
        raise AppError(ErrorCode.SANDBOX_FAILED, "非法工作区路径") from e
    return target
