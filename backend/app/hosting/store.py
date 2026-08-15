"""产物托管：local | s3 后端（B6），默认 local 目录 HOSTING_ROOT/{game_id}/{version}/。"""

import uuid
from pathlib import Path

from app.hosting.backend import ArtifactFileMeta
from app.hosting.factory import get_hosting_backend


async def write_artifact(
    game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
) -> Path:
    return await get_hosting_backend().write_artifact(game_id, version, files)


async def write_version_layers(
    game_id: uuid.UUID,
    version: int,
    *,
    source: dict[str, bytes],
    build_snapshot: dict[str, bytes],
    dist: dict[str, bytes],
) -> Path:
    from app.hosting import local as local_store

    return await local_store.write_version_layers(
        game_id,
        version,
        source=source,
        build_snapshot=build_snapshot,
        dist=dist,
    )


def index_path(game_id: uuid.UUID, version: int) -> Path | None:
    return get_hosting_backend().index_path(game_id, version)


async def read_bytes(game_id: uuid.UUID, version: int, rel: str) -> bytes | None:
    return await get_hosting_backend().read_bytes(game_id, version, rel)


async def write_bytes(
    game_id: uuid.UUID, version: int, rel: str, data: bytes
) -> None:
    """写入单个旁路产物文件（如 thumb.png），不强制 index.html。"""
    await get_hosting_backend().write_bytes(game_id, version, rel, data)


async def list_files(
    game_id: uuid.UUID, version: int
) -> list[ArtifactFileMeta]:
    """列出某版本产物下所有文件（扁平路径/大小/mime），目录不存在返回 []。"""
    return await get_hosting_backend().list_files(game_id, version)


def artifact_dir(game_id: uuid.UUID, version: int) -> Path:
    from app.hosting.local import artifact_dir as _local_dir

    return _local_dir(game_id, version)
