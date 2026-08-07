"""产物托管：本地静态目录 HOSTING_ROOT/{game_id}/{version}/。

docs/04：MVP 本地目录；路径 {game_id}/{version}/index.html；单产物大小上限。
真实对象存储/S3 后端留后续（接口不变）。
"""

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
    """防路径遍历：拒绝对/含 .. 的 rel，解析后必须落在 base 内。"""
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
    """写入产物文件（路径清洗 + to_thread 不阻塞事件循环），返回 index.html 路径。"""
    if "index.html" not in files:
        raise AppError(ErrorCode.SANDBOX_FAILED, "产物缺少 index.html")
    base = artifact_dir(game_id, version)
    limit = settings.artifact_max_size_mb * 1024 * 1024
    await asyncio.to_thread(_write_sync, base, files, limit)
    return base / "index.html"


def index_path(game_id: uuid.UUID, version: int) -> Path | None:
    """存在则返回 index.html 路径，否则 None。"""
    p = artifact_dir(game_id, version) / "index.html"
    return p if p.exists() else None
