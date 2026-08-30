"""Knowledge Source 归档（ADR-14 §3.6.2）。

Backend:
- local → `local://knowledge-sources/...` 落盘
- s3 → `s3://{bucket}/knowledge-sources/...`（复用托管 S3_* 凭据，独立 key 前缀）

可选写入 PostgreSQL `knowledge_sources` 元数据行。
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.core.config import settings
from app.forge.knowledge.chunk_planner import content_hash_of, normalize_text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_LOCAL_PTR_RE = re.compile(
    r"^local://knowledge-sources/"
    r"(?P<source_id>[^/]+)/"
    r"(?P<document_id>[^/]+)/"
    r"(?P<name>[a-f0-9]{16})\.md$"
)

_S3_PTR_RE = re.compile(
    r"^s3://(?P<bucket>[^/]+)/"
    r"(?P<key>.+\.md)$"
)


def knowledge_source_root() -> Path:
    return Path(settings.knowledge_source_root).expanduser().resolve()


def _safe_segment(value: str) -> str:
    raw = (value or "").strip() or "unknown"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
    if not cleaned or cleaned in {".", ".."} or ".." in cleaned:
        return "unknown"
    return cleaned[:120]


def _digest16(content_hash: str, *, sid: str, did: str) -> str:
    digest = (content_hash or "")[:16].lower()
    if len(digest) < 16 or not re.fullmatch(r"[a-f0-9]{16}", digest):
        return content_hash_of(f"{sid}:{did}:{content_hash}")[:16]
    return digest


def build_local_content_ptr(*, source_id: str, document_id: str, content_hash: str) -> str:
    sid = _safe_segment(source_id)
    did = _safe_segment(document_id)
    digest = _digest16(content_hash, sid=sid, did=did)
    return f"local://knowledge-sources/{sid}/{did}/{digest}.md"


def build_s3_content_ptr(*, source_id: str, document_id: str, content_hash: str) -> str:
    bucket = settings.s3_bucket.strip()
    if not bucket:
        raise ValueError("S3_BUCKET required for knowledge_source_backend=s3")
    sid = _safe_segment(source_id)
    did = _safe_segment(document_id)
    digest = _digest16(content_hash, sid=sid, did=did)
    prefix = (settings.knowledge_s3_prefix or "knowledge-sources").strip().strip("/")
    key = f"{prefix}/{sid}/{did}/{digest}.md"
    return f"s3://{bucket}/{key}"


# 兼容旧名
def build_content_ptr(*, source_id: str, document_id: str, content_hash: str) -> str:
    backend = (settings.knowledge_source_backend or "local").strip().lower()
    if backend == "s3":
        return build_s3_content_ptr(
            source_id=source_id, document_id=document_id, content_hash=content_hash
        )
    return build_local_content_ptr(
        source_id=source_id, document_id=document_id, content_hash=content_hash
    )


def resolve_content_ptr(content_ptr: str) -> Path:
    """仅解析 local:// 指针。"""
    ptr = (content_ptr or "").strip()
    match = _LOCAL_PTR_RE.match(ptr)
    if not match:
        raise ValueError(f"unsupported local content_ptr: {ptr!r}")
    root = knowledge_source_root()
    sid = _safe_segment(match.group("source_id"))
    did = _safe_segment(match.group("document_id"))
    name = match.group("name")
    target = (root / "knowledge-sources" / sid / did / f"{name}.md").resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("content_ptr escapes knowledge_source_root") from exc
    return target


def _archive_local(cleaned: str, *, source_id: str, document_id: str, digest: str) -> str:
    ptr = build_local_content_ptr(source_id=source_id, document_id=document_id, content_hash=digest)
    path = resolve_content_ptr(ptr)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(cleaned, encoding="utf-8")
    return ptr


def _s3_client():  # type: ignore[no-untyped-def]
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
        raise ValueError(f"S3 knowledge archive missing config: {', '.join(missing)}")
    import boto3  # type: ignore[import-untyped]
    from botocore.config import Config  # type: ignore[import-untyped]

    return boto3.client(
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
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


async def _archive_s3(cleaned: str, *, source_id: str, document_id: str, digest: str) -> str:
    ptr = build_s3_content_ptr(source_id=source_id, document_id=document_id, content_hash=digest)
    parsed = urlparse(ptr)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    def _put() -> None:
        client = _s3_client()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=cleaned.encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
        )

    await asyncio.to_thread(_put)
    return ptr


async def _read_s3(content_ptr: str) -> str:
    match = _S3_PTR_RE.match(content_ptr.strip())
    if not match:
        raise ValueError(f"unsupported s3 content_ptr: {content_ptr!r}")
    bucket = match.group("bucket")
    key = match.group("key")

    def _get() -> bytes:
        client = _s3_client()
        resp = client.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read()
        return bytes(body)

    raw = await asyncio.to_thread(_get)
    return bytes(raw).decode("utf-8")


async def _persist_db_row(
    session: AsyncSession,
    *,
    source_id: str,
    document_id: str,
    content_hash: str,
    content_ptr: str,
    title: str,
    locale: str,
    byte_size: int,
    backend: str,
) -> None:
    from sqlalchemy import select

    from app.models.knowledge_source import KnowledgeSource

    existing = await session.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.source_id == source_id,
            KnowledgeSource.document_id == document_id,
            KnowledgeSource.content_hash == content_hash,
        )
    )
    if existing is not None:
        existing.content_ptr = content_ptr
        existing.title = title[:500]
        existing.byte_size = byte_size
        existing.backend = backend
        return
    session.add(
        KnowledgeSource(
            source_id=source_id,
            document_id=document_id,
            content_hash=content_hash,
            content_ptr=content_ptr,
            title=title[:500],
            locale=locale,
            byte_size=byte_size,
            backend=backend,
        )
    )


async def archive_source(
    text: str,
    *,
    source_id: str,
    document_id: str,
    title: str = "",
    locale: str = "zh-CN",
    session: AsyncSession | None = None,
) -> str:
    """归档原文并返回 content_ptr；可选写入 knowledge_sources 表。"""
    cleaned = normalize_text(text)
    digest = content_hash_of(cleaned)
    backend = (settings.knowledge_source_backend or "local").strip().lower()
    if backend == "s3":
        ptr = await _archive_s3(
            cleaned, source_id=source_id, document_id=document_id, digest=digest
        )
    else:
        ptr = _archive_local(cleaned, source_id=source_id, document_id=document_id, digest=digest)
        backend = "local"
    if session is not None:
        await _persist_db_row(
            session,
            source_id=_safe_segment(source_id),
            document_id=_safe_segment(document_id),
            content_hash=digest,
            content_ptr=ptr,
            title=title,
            locale=locale,
            byte_size=len(cleaned.encode("utf-8")),
            backend=backend,
        )
        await session.commit()
    return ptr


def archive_source_text(
    text: str,
    *,
    source_id: str,
    document_id: str,
) -> str:
    """同步本地归档（兼容旧调用）；s3 backend 请用 archive_source。"""
    cleaned = normalize_text(text)
    digest = content_hash_of(cleaned)
    return _archive_local(cleaned, source_id=source_id, document_id=document_id, digest=digest)


def read_source_text(content_ptr: str) -> str:
    """同步读取 local:// 指针。"""
    path = resolve_content_ptr(content_ptr)
    if not path.is_file():
        raise FileNotFoundError(content_ptr)
    return path.read_text(encoding="utf-8")


async def read_source(content_ptr: str) -> str:
    """读取 local:// 或 s3:// 原文（runtime small-to-big 入口）。"""
    ptr = (content_ptr or "").strip()
    if ptr.startswith("local://"):
        return read_source_text(ptr)
    if ptr.startswith("s3://"):
        return await _read_s3(ptr)
    raise ValueError(f"unsupported content_ptr scheme: {ptr!r}")
