"""S3 兼容托管（兼容阿里云 OSS）。"""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path, PurePosixPath

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.hosting import local as local_store
from app.hosting.backend import ArtifactFileMeta


def _object_key(prefix: str, game_id: uuid.UUID, version: int, rel: str) -> str:
    """构造 S3/OSS 对象键，校验相对路径合法。

    场景：S3HostingBackend 读写列举。
    参数：prefix - 桶内前缀；game_id、version、rel。
    返回：完整 object key 字符串。
    """
    path = PurePosixPath(rel.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise AppError(ErrorCode.SANDBOX_FAILED, "非法产物路径")
    key = f"{game_id}/{version}/{path.as_posix()}"
    clean_prefix = prefix.strip("/")
    return f"{clean_prefix}/{key}" if clean_prefix else key


class S3HostingBackend:
    def __init__(self) -> None:
        """初始化 boto3 S3 客户端并校验必填配置。

        场景：HOSTING_BACKEND=s3 时构造后端。
        参数：无（读 settings）。
        返回：无；缺配置或 boto3 未安装时抛 AppError。
        """
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
                # 阿里云 OSS 不支持新版 botocore 默认的 STREAMING-UNSIGNED-PAYLOAD-TRAILER
                # 流式签名（put_object 会返回 NotImplemented）；改为按需计算校验和，
                # 与 AWS S3 行为一致，OSS/MinIO 等兼容实现都能正常上传。
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        self._bucket = settings.s3_bucket
        self._prefix = settings.s3_prefix.strip("/")

    def _key(self, game_id: uuid.UUID, version: int, rel: str) -> str:
        """带实例 prefix 的 object key 快捷方法。

        场景：put_object / get_object。
        参数：game_id、version、rel。
        返回：完整 S3 key。
        """
        return _object_key(self._prefix, game_id, version, rel)

    def _dir_prefix(self, game_id: uuid.UUID, version: int) -> str:
        """某版本产物目录的 OSS 前缀，末尾带 /。用于 list_objects。

        末尾 / 不可省：否则 version=1 会字符串匹配到 version=10/11。
        """
        clean_prefix = self._prefix.strip("/")
        head = f"{clean_prefix}/" if clean_prefix else ""
        return f"{head}{game_id}/{version}/"

    async def write_artifact(
        self, game_id: uuid.UUID, version: int, files: dict[str, str | bytes]
    ) -> Path:
        """上传版本产物到 OSS 并同步写本地缓存。

        场景：Forge promote 后持久化 dist。
        参数：game_id、version、files（须含 index.html）。
        返回：本地 index.html Path（供 FileResponse）。
        """
        if "index.html" not in files:
            raise AppError(ErrorCode.SANDBOX_FAILED, "产物缺少 index.html")

        def _upload() -> None:
            """同步上传 files 中全部对象到 OSS（在 to_thread 中执行）。

            场景：write_artifact 批量落盘。
            返回：无。
            """
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
        """委托本地缓存查询 index.html 路径。

        场景：试玩路由快速直出。
        参数：game_id、version。
        返回：Path 或 None。
        """
        return local_store.index_path(game_id, version)

    async def read_bytes(self, game_id: uuid.UUID, version: int, rel: str) -> bytes | None:
        """从 OSS 读取单个产物文件（NoSuchKey 返回 None）。

        场景：下载、回源读旁路文件。
        参数：game_id、version、rel。
        返回：bytes 或 None。
        """

        def _get() -> bytes | None:
            """同步从 OSS get_object 读取单文件。

            场景：read_bytes 在 to_thread 中调用 boto3。
            返回：文件字节；NoSuchKey 等为 None。
            """
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

    async def write_bytes(self, game_id: uuid.UUID, version: int, rel: str, data: bytes) -> None:
        """上传单个旁路文件到 OSS 并同步本地缓存。

        场景：试玩缩略图 thumb.png 等。
        参数：game_id、version、rel、data。
        返回：无。
        """

        def _upload() -> None:
            """同步上传单个旁路文件到 OSS。

            场景：write_bytes 在 to_thread 中调用。
            参数：使用闭包中的 rel、data。
            返回：无。
            """
            self._client.put_object(
                Bucket=self._bucket, Key=self._key(game_id, version, rel), Body=data
            )

        try:
            await asyncio.to_thread(_upload)
        except Exception as exc:
            raise AppError(ErrorCode.SANDBOX_FAILED, "对象存储上传失败") from exc
        # 本地 cache 同步写一份，供 FileResponse / read_bytes 直出（与 write_artifact 行为一致）
        await local_store.write_bytes(game_id, version, rel, data)

    async def list_files(self, game_id: uuid.UUID, version: int) -> list[ArtifactFileMeta]:
        """列出某版本产物下所有文件。真相源 = OSS（与 read_bytes 一致，不读本地 cache）。

        Prefix 末尾必须带 /，否则 version=1 会字符串匹配到 version=10；
        不设 Delimiter 以扁平列出全部文件（含子目录）；分页翻到 isTruncated=False。
        """

        def _list() -> list[ArtifactFileMeta]:
            """同步分页列举 OSS 前缀下全部对象。

            场景：list_files 在 to_thread 中调用。
            返回：ArtifactFileMeta 列表。
            """
            prefix = self._dir_prefix(game_id, version)
            paginator: list[ArtifactFileMeta] = []
            continuation: str | None = None
            while True:
                kwargs: dict[str, object] = {
                    "Bucket": self._bucket,
                    "Prefix": prefix,
                }
                if continuation:
                    kwargs["ContinuationToken"] = continuation
                resp = self._client.list_objects_v2(**kwargs)
                for obj in resp.get("Contents", []) or []:
                    key = obj["Key"]
                    # 跳过目录占位对象（OSS/S3 常以 key 结尾 / 表示空目录）
                    if key.endswith("/"):
                        continue
                    rel = key[len(prefix) :]
                    mime, _ = mimetypes.guess_type(rel)
                    paginator.append(
                        ArtifactFileMeta(path=rel, size=int(obj.get("Size", 0)), mime=mime)
                    )
                if not resp.get("IsTruncated"):
                    break
                continuation = resp.get("NextContinuationToken")
                if not continuation:
                    break
            paginator.sort(key=lambda m: m.path)
            return paginator

        try:
            return await asyncio.to_thread(_list)
        except Exception as exc:
            raise AppError(ErrorCode.SANDBOX_FAILED, "对象存储列举失败") from exc

    async def write_version_layers(
        self,
        game_id: uuid.UUID,
        version: int,
        *,
        source: dict[str, bytes],
        build_snapshot: dict[str, bytes],
        dist: dict[str, bytes],
    ) -> Path:
        """三层产物经本后端 write_artifact 上传（OSS SoT + 本地 cache）。"""
        if "index.html" not in dist:
            raise AppError(ErrorCode.SANDBOX_FAILED, "dist 缺少 index.html")
        source_limit = settings.source_artifact_max_size_mb * 1024 * 1024
        source_bytes = local_store._layer_bytes(source)
        if source_bytes > source_limit:
            raise AppError(
                ErrorCode.QUOTA_EXCEEDED,
                f"source 产物超出大小上限（{source_bytes} > {source_limit}）",
            )
        combined: dict[str, bytes] = dict(dist)
        combined.update(local_store._prefix_files("source", source))  # type: ignore[arg-type]
        combined.update(local_store._prefix_files("build", build_snapshot))  # type: ignore[arg-type]
        return await self.write_artifact(game_id, version, dict(combined))
