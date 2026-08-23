"""产物托管：local | s3 后端（B6），默认 local 目录 HOSTING_ROOT/{game_id}/{version}/。"""

import uuid
from pathlib import Path

from app.hosting.backend import ArtifactFileMeta
from app.hosting.factory import get_hosting_backend


async def write_artifact(game_id: uuid.UUID, version: int, files: dict[str, str | bytes]) -> Path:
    """委托当前 Hosting 后端写入单层产物。

    场景：Forge promote 后统一入口。
    参数：game_id、version、files。
    返回：index.html Path。
    """
    return await get_hosting_backend().write_artifact(game_id, version, files)


async def write_version_layers(
    game_id: uuid.UUID,
    version: int,
    *,
    source: dict[str, bytes],
    build_snapshot: dict[str, bytes],
    dist: dict[str, bytes],
) -> Path:
    """委托后端写入 source/build/dist 三层产物。

    场景：Code QA 成功后分层落盘。
    参数：game_id、version、source、build_snapshot、dist。
    返回：index.html Path。
    """
    return await get_hosting_backend().write_version_layers(
        game_id,
        version,
        source=source,
        build_snapshot=build_snapshot,
        dist=dist,
    )


def index_path(game_id: uuid.UUID, version: int) -> Path | None:
    """返回当前后端下 index.html 本地路径（存在时）。

    场景：试玩路由判断产物是否已落盘。
    参数：game_id、version。
    返回：Path 或 None。
    """
    return get_hosting_backend().index_path(game_id, version)


async def read_bytes(game_id: uuid.UUID, version: int, rel: str) -> bytes | None:
    """委托后端按相对路径读取单个产物文件。

    场景：封面 thumb、owner 下载等。
    参数：game_id、version、rel。
    返回：文件 bytes 或 None。
    """
    return await get_hosting_backend().read_bytes(game_id, version, rel)


async def write_bytes(game_id: uuid.UUID, version: int, rel: str, data: bytes) -> None:
    """写入单个旁路产物文件（如 thumb.png），不强制 index.html。"""
    await get_hosting_backend().write_bytes(game_id, version, rel, data)


async def list_files(game_id: uuid.UUID, version: int) -> list[ArtifactFileMeta]:
    """列出某版本产物下所有文件（扁平路径/大小/mime），目录不存在返回 []。"""
    return await get_hosting_backend().list_files(game_id, version)


def artifact_dir(game_id: uuid.UUID, version: int) -> Path:
    """返回本地产物目录路径（始终走 local 布局）。

    场景：试玩路由 FileResponse 直出、多语言 index 探测。
    参数：game_id、version。
    返回：{hosting_root}/{game_id}/{version} Path。
    """
    from app.hosting.local import artifact_dir as _local_dir

    return _local_dir(game_id, version)
