"""Hosting 存储后端抽象（B6）：local | s3。"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol


class HostingBackend(Protocol):
    async def write_artifact(
        self, game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
    ) -> Path: ...

    def index_path(self, game_id: uuid.UUID, version: int) -> Path | None: ...

    async def read_bytes(self, game_id: uuid.UUID, version: int, rel: str) -> bytes | None: ...

    async def write_bytes(
        self, game_id: uuid.UUID, version: int, rel: str, data: bytes
    ) -> None: ...
