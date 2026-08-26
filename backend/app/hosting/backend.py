"""Hosting 存储后端抽象（B6）：local | s3。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ArtifactFileMeta:
    """产物单个文件的中性描述（不含 game_id/version，由调用方持有上下文）。

    path 是相对产物根目录的 POSIX 风格路径（如 "index.html"、"assets/app.js"），
    供前端直接渲染文件树；size 为字节数；mime 由 mimetypes 推断，拿不到为 None。
    """

    path: str
    size: int
    mime: str | None


class HostingBackend(Protocol):
    async def write_artifact(
        self, game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
    ) -> Path: ...

    async def write_native_artifact(
        self, game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
    ) -> Path: ...

    async def write_version_layers(
        self,
        game_id: uuid.UUID,
        version: int,
        *,
        source: dict[str, bytes],
        build_snapshot: dict[str, bytes],
        dist: dict[str, bytes],
    ) -> Path: ...

    def index_path(self, game_id: uuid.UUID, version: int) -> Path | None: ...

    async def read_bytes(self, game_id: uuid.UUID, version: int, rel: str) -> bytes | None: ...

    async def write_bytes(
        self, game_id: uuid.UUID, version: int, rel: str, data: bytes
    ) -> None: ...

    async def list_files(self, game_id: uuid.UUID, version: int) -> list[ArtifactFileMeta]: ...
