"""S3 兼容托管（兼容阿里云 OSS）。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path, PurePosixPath

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.hosting import local as local_store


def _object_key(prefix: str, game_id: uuid.UUID, version: int, rel: str) -> str:
    path = PurePosixPath(rel.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise AppError(ErrorCode.SANDBOX_FAILED, "非法产物路径")
    key = f"{game_id}/{version}/{path.as_posix()}"
    clean_prefix = prefix.strip("/")
    return f"{clean_prefix}/{key}" if clean_prefix else key


class S3HostingBackend:
    def __init__(self) -> None:
        missing = [
            name
            for name, value in (
                ("S3_BUCKET", settings.s3_bucket),
                ("S3_AK", settings.s3_ak),
                ("S3_SK", settings.s3_sk),
                ("S3_ENDPOINT", settings.s3_endpoint),
                ("S3_REGION", settings.s3_region),
            )
            if not value
        ]
        if missing:
            raise AppError(ErrorCode.SANDBOX_FAILED, f"S3 托管缺少配置: {', '.join(missing)}")
        try:
            import boto3  # type: ignore[import-untyped]
            from botocore.config import Config  # type: ignore[import-untyped]
        except ImportError as e:
            raise AppError(ErrorCode.SANDBOX_FAILED, "boto3 未安装，无法启用 S3 托管") from e
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint.rstrip("/"),
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_ak,
            aws_secret_access_key=settings.s3_sk,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.s3_addressing_style},
                connect_timeout=settings.s3_connect_timeout,
                read_timeout=settings.s3_read_timeout,
            ),
        )
        self._bucket = settings.s3_bucket
        self._prefix = settings.s3_prefix.strip("/")

    def _key(self, game_id: uuid.UUID, version: int, rel: str) -> str:
        return _object_key(self._prefix, game_id, version, rel)

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

        try:
            await asyncio.to_thread(_upload)
        except Exception as exc:
            raise AppError(ErrorCode.SANDBOX_FAILED, "对象存储上传失败") from exc
        # 保留本地缓存供当前实例快速直出；缓存丢失时由 read_bytes 从 OSS 回源。
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
            except Exception as exc:  # noqa: BLE001
                response = getattr(exc, "response", {})
                code = str(response.get("Error", {}).get("Code", ""))
                if code in {"NoSuchKey", "NoSuchObject", "404"}:
                    return None
                raise AppError(ErrorCode.SANDBOX_FAILED, "对象存储读取失败") from exc

        return await asyncio.to_thread(_get)

    async def write_bytes(
        self, game_id: uuid.UUID, version: int, rel: str, data: bytes
    ) -> None:
        def _upload() -> None:
            self._client.put_object(
                Bucket=self._bucket, Key=self._key(game_id, version, rel), Body=data
            )

        try:
            await asyncio.to_thread(_upload)
        except Exception as exc:
            raise AppError(ErrorCode.SANDBOX_FAILED, "对象存储上传失败") from exc
        # 本地 cache 同步写一份，供 FileResponse / read_bytes 直出（与 write_artifact 行为一致）
        await local_store.write_bytes(game_id, version, rel, data)
