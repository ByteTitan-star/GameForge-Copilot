"""产物采集：按 collect_root 收集静态文件并校验 index.html。"""

from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


def collect_artifact_files(
    workspace: Path,
    *,
    collect_root: str = ".",
    max_size_mb: int | None = None,
) -> dict[str, bytes]:
    """采集 workspace 下 collect_root 目录内的文件，键为相对 collect_root 的路径。"""
    base = workspace if collect_root in (".", "") else workspace / collect_root
    if not base.is_dir():
        raise AppError(ErrorCode.SANDBOX_FAILED, f"产物目录不存在: {collect_root}")

    limit = (max_size_mb or settings.artifact_max_size_mb) * 1024 * 1024
    files: dict[str, bytes] = {}
    total = 0
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        data = p.read_bytes()
        total += len(data)
        if total > limit:
            raise AppError(ErrorCode.QUOTA_EXCEEDED, "产物超出大小上限")
        files[str(p.relative_to(base).as_posix())] = data
    return files
