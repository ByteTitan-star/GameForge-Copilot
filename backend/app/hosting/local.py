"""本地托管实现（从 store 拆出，供 local/S3 复用）。"""

import asyncio
import mimetypes
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.hosting.backend import ArtifactFileMeta


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


def _is_within(base_resolved: Path, target: Path) -> bool:
    """target 是否落在 base_resolved 内（含 base 自身）。供列目录等批量场景复用。

    与 _check_path 同款校验逻辑，但不抛错、不读 rel——调用方已拿到真实 target。
    防御符号链接/异常文件名泄漏到前端。
    """
    if target == base_resolved:
        return True
    return base_resolved in target.parents


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


def _prefix_files(prefix: str, files: dict[str, str | bytes]) -> dict[str, str | bytes]:
    return {f"{prefix}/{rel}": content for rel, content in files.items()}


def _layer_bytes(files: dict[str, bytes]) -> int:
    return sum(len(v) for v in files.values())


async def write_version_layers(
    game_id: uuid.UUID,
    version: int,
    *,
    source: dict[str, bytes],
    build_snapshot: dict[str, bytes],
    dist: dict[str, bytes],
) -> Path:
    """三层产物：dist 在版本根（兼容试玩路由），source/build 在子目录（§12）。"""
    if "index.html" not in dist:
        raise AppError(ErrorCode.SANDBOX_FAILED, "dist 缺少 index.html")
    source_limit = settings.source_artifact_max_size_mb * 1024 * 1024
    source_bytes = _layer_bytes(source)
    if source_bytes > source_limit:
        raise AppError(
            ErrorCode.QUOTA_EXCEEDED,
            f"source 产物超出大小上限（{source_bytes} > {source_limit}）",
        )
    combined: dict[str, bytes] = dict(dist)
    combined.update(_prefix_files("source", source))
    combined.update(_prefix_files("build", build_snapshot))
    return await write_artifact(game_id, version, combined)


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


def _write_bytes_sync(base: Path, rel: str, data: bytes) -> None:
    # 产物目录可能尚未存在（首版截图先于 index.html 落盘的场景不多，但这里不依赖外部保证）。
    base.mkdir(parents=True, exist_ok=True)
    target = _check_path(base.resolve(), rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


async def write_bytes(
    game_id: uuid.UUID, version: int, rel: str, data: bytes
) -> None:
    """写入单个旁路产物文件（如 thumb.png），复用 _check_path 防穿越，不强制 index.html。"""
    await asyncio.to_thread(_write_bytes_sync, artifact_dir(game_id, version), rel, data)


def _list_files_sync(base: Path) -> list[ArtifactFileMeta]:
    if not base.is_dir():
        # 目录不存在（版本未生成/已清理）视为空，不抛错——与空目录一视同仁。
        return []
    base_r = base.resolve()
    metas: list[ArtifactFileMeta] = []
    for target in base.rglob("*"):
        if not target.is_file():
            continue
        resolved = target.resolve()
        if not _is_within(base_r, resolved):
            continue
        rel = resolved.relative_to(base_r).as_posix()
        size = resolved.stat().st_size
        mime, _ = mimetypes.guess_type(rel)
        metas.append(ArtifactFileMeta(path=rel, size=size, mime=mime))
    metas.sort(key=lambda m: m.path)
    return metas


async def list_files(
    game_id: uuid.UUID, version: int
) -> list[ArtifactFileMeta]:
    """列出某版本产物下所有文件（扁平，含相对路径/大小/mime）。

    仅供 owner 端点消费；防御性过滤越界文件。目录不存在返回 []。
    """
    return await asyncio.to_thread(_list_files_sync, artifact_dir(game_id, version))
