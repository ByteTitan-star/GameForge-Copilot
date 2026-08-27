"""Curated Knowledge Ingestion（ADR-14 §3.5；Runtime Agent 禁止调用）。"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.forge.knowledge.guards import (
    current_embedding_version_tag,
    validate_embedding_model_configured,
)
from app.forge.knowledge.pinecone_store import get_knowledge_pinecone_store
from app.forge.knowledge.schema import metadata_validation_error
from app.llm.embeddings import embed_one

_REQUIRED_CHUNK_KEYS = frozenset({"chunk_id", "text", "domain", "category", "title", "source_id"})


@dataclass(frozen=True)
class KnowledgeChunkSpec:
    chunk_id: str
    text: str
    domain: str
    category: str
    title: str
    source_id: str
    tags: tuple[str, ...] = ()
    quality_tier: str = "silver"
    acl: str = "internal"
    source_kind: str = "curated"
    locale: str = "zh-CN"


@dataclass(frozen=True)
class IngestResult:
    total: int
    upserted: int
    skipped: int
    errors: tuple[str, ...]


def _json_safe_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in meta.items():
        if isinstance(val, (str, int, float, bool)) or val is None:
            out[key] = val if val is not None else ""
        else:
            out[key] = json.dumps(val, ensure_ascii=False, default=str)
    return out


def parse_corpus_document(data: object) -> list[KnowledgeChunkSpec]:
    """解析 JSON corpus：`{"chunks": [...]}` 或顶层数组。"""
    if isinstance(data, list):
        raw_chunks = data
    elif isinstance(data, dict):
        raw = data.get("chunks")
        if not isinstance(raw, list):
            msg = 'corpus must be a list or {"chunks": [...]}'
            raise ValueError(msg)
        raw_chunks = raw
    else:
        raise ValueError("corpus JSON root must be object or array")

    specs: list[KnowledgeChunkSpec] = []
    for idx, item in enumerate(raw_chunks):
        if not isinstance(item, dict):
            raise ValueError(f"chunk[{idx}] must be an object")
        missing = _REQUIRED_CHUNK_KEYS - item.keys()
        if missing:
            raise ValueError(f"chunk[{idx}] missing keys: {sorted(missing)}")
        tags_raw = item.get("tags") or []
        tags: tuple[str, ...]
        if isinstance(tags_raw, list):
            tags = tuple(str(t) for t in tags_raw)
        elif isinstance(tags_raw, str):
            tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())
        else:
            tags = ()
        domain = str(item["domain"]).strip()
        category = str(item["category"]).strip()
        quality_tier = str(item.get("quality_tier") or "silver")
        acl = str(item.get("acl") or "internal")
        if settings.knowledge_metadata_validation_enabled:
            err = metadata_validation_error(
                domain=domain,
                category=category,
                acl=acl,
                quality_tier=quality_tier,
            )
            if err:
                raise ValueError(f"chunk[{idx}] {err}")
        specs.append(
            KnowledgeChunkSpec(
                chunk_id=str(item["chunk_id"]).strip(),
                text=str(item["text"]).strip(),
                domain=domain,
                category=category,
                title=str(item["title"]).strip(),
                source_id=str(item["source_id"]).strip(),
                tags=tags,
                quality_tier=quality_tier,
                acl=acl,
                source_kind=str(item.get("source_kind") or "curated"),
                locale=str(item.get("locale") or "zh-CN"),
            )
        )
    return specs


def load_corpus_file(path: Path) -> list[KnowledgeChunkSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_corpus_document(data)


async def upsert_knowledge_chunk(
    *,
    chunk_id: str,
    text: str,
    domain: str,
    category: str,
    title: str,
    source_id: str,
    tags: list[str] | None = None,
    quality_tier: str = "silver",
    acl: str = "internal",
    source_kind: str = "curated",
    locale: str = "zh-CN",
) -> bool:
    store = get_knowledge_pinecone_store()
    if store is None:
        return False
    body = text.strip()
    if not body:
        return False
    if settings.knowledge_metadata_validation_enabled:
        err = metadata_validation_error(
            domain=domain,
            category=category,
            acl=acl,
            quality_tier=quality_tier,
        )
        if err:
            return False
    if not validate_embedding_model_configured():
        return False
    vector = await embed_one(body)
    if vector is None:
        return False
    expected_dim = int(settings.knowledge_embedding_expected_dim)
    if expected_dim > 0 and len(vector) != expected_dim:
        return False
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    embedding_version = current_embedding_version_tag()
    meta: dict[str, Any] = {
        "domain": domain,
        "category": category,
        "title": title[:500],
        "chunk_id": chunk_id,
        "source_id": source_id,
        "source_kind": source_kind,
        "locale": locale,
        "tags": ",".join(tags or []),
        "quality_tier": quality_tier,
        "acl": acl,
        "trust_level": source_kind,
        "text": body[:4000],
        "content_hash": content_hash,
        "created_at": int(time.time()),
    }
    if embedding_version:
        meta["embedding_version"] = embedding_version
    await store.upsert(
        vector_id=chunk_id,
        values=vector,
        metadata=_json_safe_meta(meta),
    )
    return True


async def upsert_knowledge_spec(spec: KnowledgeChunkSpec) -> bool:
    return await upsert_knowledge_chunk(
        chunk_id=spec.chunk_id,
        text=spec.text,
        domain=spec.domain,
        category=spec.category,
        title=spec.title,
        source_id=spec.source_id,
        tags=list(spec.tags),
        quality_tier=spec.quality_tier,
        acl=spec.acl,
        source_kind=spec.source_kind,
        locale=spec.locale,
    )


async def ingest_corpus(
    chunks: list[KnowledgeChunkSpec],
    *,
    dry_run: bool = False,
) -> IngestResult:
    if dry_run:
        valid = sum(1 for c in chunks if c.text.strip() and c.chunk_id)
        return IngestResult(
            total=len(chunks),
            upserted=valid,
            skipped=len(chunks) - valid,
            errors=(),
        )

    if get_knowledge_pinecone_store() is None:
        return IngestResult(
            total=len(chunks),
            upserted=0,
            skipped=len(chunks),
            errors=(
                "knowledge pinecone not configured: set PINECONE_KNOWLEDGE_HOST "
                "(independent from PINECONE_HOST)",
            ),
        )

    upserted = 0
    skipped = 0
    errors: list[str] = []
    for spec in chunks:
        if not spec.chunk_id or not spec.text.strip():
            skipped += 1
            continue
        try:
            ok = await upsert_knowledge_spec(spec)
        except Exception as exc:  # noqa: BLE001 — 单条失败不阻断整批
            errors.append(f"{spec.chunk_id}: {type(exc).__name__}")
            skipped += 1
            continue
        if ok:
            upserted += 1
        else:
            skipped += 1
            errors.append(f"{spec.chunk_id}: upsert returned false")
    return IngestResult(
        total=len(chunks),
        upserted=upserted,
        skipped=skipped,
        errors=tuple(errors),
    )


async def ingest_corpus_file(path: Path, *, dry_run: bool = False) -> IngestResult:
    chunks = load_corpus_file(path)
    return await ingest_corpus(chunks, dry_run=dry_run)
