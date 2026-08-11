"""本地托管实现（从 store 拆出，供 local/S3 复用）。"""

import asyncio
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


def _root() -> Path:
    return Path(settings.hosting_root)


def artifact_dir(game_id: uuid.UUID, version: int) -> Path:
    return _root() / str(game_id) / str(version)


def _check_path(base_resolved: Path, rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise AppError(ErrorCode.SANDBOX_FAILED, "非法产物路径")
    target = (base_resolved / p).resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise AppError(ErrorCode.SANDBOX_FAILED, "非法产物路径")
    return target


def _write_sync(base: Path, files: dict[str, str | bytes], limit: int) -> None:
    base.mkdir(parents=True, exist_ok=True)
    base_r = base.resolve()
    total = 0
    for rel, content in files.items():
        data = content.encode() if isinstance(content, str) else content
        total += len(data)
        if total > limit:
            raise AppError(ErrorCode.QUOTA_EXCEEDED, "产物超出大小上限")
        target = _check_path(base_r, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


async def write_artifact(
    game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
) -> Path:
    if "index.html" not in files:
        raise AppError(ErrorCode.SANDBOX_FAILED, "产物缺少 index.html")
    base = artifact_dir(game_id, version)
    limit = settings.artifact_max_size_mb * 1024 * 1024
    await asyncio.to_thread(_write_sync, base, files, limit)
    return base / "index.html"


def index_path(game_id: uuid.UUID, version: int) -> Path | None:
    p = artifact_dir(game_id, version) / "index.html"
    return p if p.exists() else None


def _read_bytes_sync(base: Path, rel: str) -> bytes | None:
    if not base.exists():
        return None
    target = _check_path(base.resolve(), rel)
    return target.read_bytes() if target.is_file() else None


async def read_bytes(game_id: uuid.UUID, version: int, rel: str) -> bytes | None:
    """Read a single artifact file without exposing the hosting root to callers."""
    return await asyncio.to_thread(_read_bytes_sync, artifact_dir(game_id, version), rel)
