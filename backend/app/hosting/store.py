"""产物托管：local | s3 后端（B6），默认 local 目录 HOSTING_ROOT/{game_id}/{version}/。"""

import uuid
from pathlib import Path

from app.hosting.factory import get_hosting_backend


async def write_artifact(
    game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
) -> Path:
    return await get_hosting_backend().write_artifact(game_id, version, files)


def index_path(game_id: uuid.UUID, version: int) -> Path | None:
    return get_hosting_backend().index_path(game_id, version)


async def read_bytes(game_id: uuid.UUID, version: int, rel: str) -> bytes | None:
    return await get_hosting_backend().read_bytes(game_id, version, rel)


async def write_bytes(
    game_id: uuid.UUID, version: int, rel: str, data: bytes
) -> None:
    """写入单个旁路产物文件（如 thumb.png），不强制 index.html。"""
    await get_hosting_backend().write_bytes(game_id, version, rel, data)


def artifact_dir(game_id: uuid.UUID, version: int) -> Path:
    from app.hosting.local import artifact_dir as _local_dir

    return _local_dir(game_id, version)
