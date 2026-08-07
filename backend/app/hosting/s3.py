"""S3 兼容托管（B6）。未配置 boto3/凭证时由 factory 回退 local。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.hosting import local as local_store


class S3HostingBackend:
    def __init__(self) -> None:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as e:
            raise AppError(ErrorCode.SANDBOX_FAILED, "boto3 未安装，无法启用 S3 托管") from e
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_ak or None,
            aws_secret_access_key=settings.s3_sk or None,
        )
        self._bucket = settings.s3_bucket
        self._cache = Path(settings.hosting_root) / ".s3-cache"

    def _key(self, game_id: uuid.UUID, version: int, rel: str) -> str:
        return f"{game_id}/{version}/{rel}"

    async def write_artifact(
        self, game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
    ) -> Path:
        if "index.html" not in files:
            raise AppError(ErrorCode.SANDBOX_FAILED, "产物缺少 index.html")

        def _upload() -> None:
            for rel, content in files.items():
                body = content.encode() if isinstance(content, str) else content
                self._client.put_object(
                    Bucket=self._bucket, Key=self._key(game_id, version, rel), Body=body
                )

        await asyncio.to_thread(_upload)
        # 本地 cache 供 FileResponse 直出（生产可换 presigned URL）
        return await local_store.write_artifact(game_id, version, files)

    def index_path(self, game_id: uuid.UUID, version: int) -> Path | None:
        return local_store.index_path(game_id, version)

    async def read_bytes(self, game_id: uuid.UUID, version: int, rel: str) -> bytes | None:
        def _get() -> bytes | None:
            try:
                obj = self._client.get_object(
                    Bucket=self._bucket, Key=self._key(game_id, version, rel)
                )
                return obj["Body"].read()
            except Exception:  # noqa: BLE001
                return None

        return await asyncio.to_thread(_get)
