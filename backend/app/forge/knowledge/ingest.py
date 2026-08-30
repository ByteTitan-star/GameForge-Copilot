"""Curated Knowledge Ingestion（ADR-14 §3.5 / §3.6；Runtime Agent 禁止调用）。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.forge.knowledge.chunk_planner import (
    assert_no_truncation,
    content_hash_of,
    plan_markdown,
)
from app.forge.knowledge.chunk_policy import (
    EMBED_MAX_TOKENS,
    effective_max_tokens,
    policy_for_category,
)
from app.forge.knowledge.guards import (
    current_embedding_version_tag,
    validate_embedding_model_configured,
)
from app.forge.knowledge.pinecone_store import get_knowledge_writer
from app.forge.knowledge.schema import metadata_validation_error
from app.forge.memory.context_builder import estimate_tokens
from app.llm.embeddings import embed_one

_REQUIRED_CHUNK_KEYS = frozenset({"chunk_id", "text", "domain", "category", "title", "source_id"})
_METADATA_TEXT_MAX_CHARS = 2000


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
    document_id: str = ""
    chunk_index: int = 0
    chunk_total: int = 1
    chunk_policy: str = ""
    parent_chunk_id: str = ""
    content_ptr: str = ""
    content_hash: str = ""


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


def _parse_one_chunk(item: dict[str, Any], idx: int) -> KnowledgeChunkSpec:
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
    text = str(item["text"]).strip()
    policy_name = str(item.get("chunk_policy") or "").strip()
    if not policy_name:
        policy_name = policy_for_category(category).name
    doc_id = str(item.get("document_id") or item.get("source_id") or "").strip()
    chunk_id = str(item["chunk_id"]).strip()
    return KnowledgeChunkSpec(
        chunk_id=chunk_id,
        text=text,
        domain=domain,
        category=category,
        title=str(item["title"]).strip(),
        source_id=str(item["source_id"]).strip(),
        tags=tags,
        quality_tier=quality_tier,
        acl=acl,
        source_kind=str(item.get("source_kind") or "curated"),
        locale=str(item.get("locale") or "zh-CN"),
        document_id=doc_id,
        chunk_index=int(item.get("chunk_index") or 0),
        chunk_total=int(item.get("chunk_total") or 1),
        chunk_policy=policy_name,
        parent_chunk_id=str(item.get("parent_chunk_id") or ""),
        content_ptr=str(item.get("content_ptr") or ""),
        content_hash=str(item.get("content_hash") or content_hash_of(text)),
    )


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
        specs.append(_parse_one_chunk(item, idx))
    return specs


def load_corpus_file(path: Path) -> list[KnowledgeChunkSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_corpus_document(data)


def specs_from_markdown(
    markdown: str,
    *,
    document_id: str,
    domain: str,
    category: str,
    title: str,
    source_id: str,
    policy_name: str | None = None,
    content_ptr: str = "",
    tags: tuple[str, ...] = (),
    quality_tier: str = "silver",
    acl: str = "internal",
) -> list[KnowledgeChunkSpec]:
    """Markdown → ChunkPlanner → KnowledgeChunkSpec[]。"""
    drafts = plan_markdown(markdown, category=category, policy_name=policy_name)
    if assert_no_truncation(drafts) > 0:
        raise ValueError("chunk planner produced oversize chunks (truncation_rate > 0)")
    total = len(drafts)
    out: list[KnowledgeChunkSpec] = []
    for draft in drafts:
        chunk_id = f"{source_id}#{document_id}#{draft.chunk_index:04d}"
        parent = (
            f"{source_id}#{document_id}#{draft.chunk_index - 1:04d}"
            if draft.chunk_index > 0
            else ""
        )
        out.append(
            KnowledgeChunkSpec(
                chunk_id=chunk_id,
                text=draft.text,
                domain=domain,
                category=category,
                title=(draft.title_hint or title)[:500],
                source_id=source_id,
                tags=tags,
                quality_tier=quality_tier,
                acl=acl,
                document_id=document_id,
                chunk_index=draft.chunk_index,
                chunk_total=total,
                chunk_policy=draft.chunk_policy,
                parent_chunk_id=parent,
                content_ptr=content_ptr,
                content_hash=content_hash_of(draft.text),
            )
        )
    return out


def _guard_embed_tokens(text: str, *, category: str, chunk_policy: str) -> str | None:
    """超 EMBED_MAX / policy max 则返回错误信息（拒绝静默截断）。"""
    from app.forge.knowledge.chunk_policy import policy_by_name

    policy = policy_by_name(chunk_policy) or policy_for_category(category)
    limit = effective_max_tokens(policy)
    tokens = estimate_tokens(text)
    if tokens > limit:
        return f"chunk exceeds token limit: {tokens} > {limit}"
    if tokens > EMBED_MAX_TOKENS:
        return f"chunk exceeds embed max: {tokens} > {EMBED_MAX_TOKENS}"
    return None


async def _content_hash_exists(content_hash: str) -> bool:
    """尽量探测 store 中是否已有同 hash（InMemory 扫描；HTTP 暂靠批内去重）。"""
    store = get_knowledge_writer()
    if store is None or not content_hash:
        return False
    rows = getattr(store, "_rows", None)
    if isinstance(rows, dict):
        for _vid, (_vec, meta) in rows.items():
            if isinstance(meta, dict) and meta.get("content_hash") == content_hash:
                return True
    return False


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
    document_id: str = "",
    chunk_index: int = 0,
    chunk_total: int = 1,
    chunk_policy: str = "",
    parent_chunk_id: str = "",
    content_ptr: str = "",
    content_hash: str = "",
    known_hashes: set[str] | None = None,
) -> str:
    """返回 'upserted' | 'skipped' | 'error'。"""
    store = get_knowledge_writer()
    if store is None:
        return "error"
    body = text.strip()
    if not body:
        return "error"
    policy_name = chunk_policy.strip() or policy_for_category(category).name
    guard_err = _guard_embed_tokens(body, category=category, chunk_policy=policy_name)
    if guard_err:
        return "error"
    if settings.knowledge_metadata_validation_enabled:
        err = metadata_validation_error(
            domain=domain,
            category=category,
            acl=acl,
            quality_tier=quality_tier,
        )
        if err:
            return "error"
    digest = content_hash or content_hash_of(body)
    if known_hashes is not None and digest in known_hashes:
        return "skipped"
    if await _content_hash_exists(digest):
        if known_hashes is not None:
            known_hashes.add(digest)
        return "skipped"
    if not validate_embedding_model_configured():
        return "error"
    vector = await embed_one(body)
    if vector is None:
        return "error"
    expected_dim = int(settings.knowledge_embedding_expected_dim)
    if expected_dim > 0 and len(vector) != expected_dim:
        return "error"
    embedding_version = current_embedding_version_tag()
    doc_id = document_id.strip() or source_id
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
        "text": body[:_METADATA_TEXT_MAX_CHARS],
        "content_hash": digest,
        "document_id": doc_id,
        "chunk_index": int(chunk_index),
        "chunk_total": int(chunk_total),
        "chunk_policy": policy_name,
        "parent_chunk_id": parent_chunk_id,
        "content_ptr": content_ptr,
        "char_count": len(body),
        "token_estimate": estimate_tokens(body),
        "created_at": int(time.time()),
    }
    if embedding_version:
        meta["embedding_version"] = embedding_version
    await store.upsert(
        vector_id=chunk_id,
        values=vector,
        metadata=_json_safe_meta(meta),
    )
    if known_hashes is not None:
        known_hashes.add(digest)
    return "upserted"


async def upsert_knowledge_spec(
    spec: KnowledgeChunkSpec,
    *,
    known_hashes: set[str] | None = None,
) -> bool:
    status = await upsert_knowledge_chunk(
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
        document_id=spec.document_id,
        chunk_index=spec.chunk_index,
        chunk_total=spec.chunk_total,
        chunk_policy=spec.chunk_policy,
        parent_chunk_id=spec.parent_chunk_id,
        content_ptr=spec.content_ptr,
        content_hash=spec.content_hash,
        known_hashes=known_hashes,
    )
    return status == "upserted"


async def ingest_corpus(
    chunks: list[KnowledgeChunkSpec],
    *,
    dry_run: bool = False,
) -> IngestResult:
    errors: list[str] = []
    if dry_run:
        valid = 0
        for c in chunks:
            if not c.text.strip() or not c.chunk_id:
                continue
            err = _guard_embed_tokens(
                c.text,
                category=c.category,
                chunk_policy=c.chunk_policy or policy_for_category(c.category).name,
            )
            if err:
                errors.append(f"{c.chunk_id}: {err}")
                continue
            valid += 1
        return IngestResult(
            total=len(chunks),
            upserted=valid,
            skipped=len(chunks) - valid,
            errors=tuple(errors),
        )

    if get_knowledge_writer() is None:
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
    known_hashes: set[str] = set()
    for spec in chunks:
        if not spec.chunk_id or not spec.text.strip():
            skipped += 1
            continue
        # JSON fast path：超限则拒绝（不静默截断）；调用方应先走 ChunkPlanner
        guard = _guard_embed_tokens(
            spec.text,
            category=spec.category,
            chunk_policy=spec.chunk_policy or policy_for_category(spec.category).name,
        )
        if guard:
            skipped += 1
            errors.append(f"{spec.chunk_id}: {guard}")
            continue
        enriched = spec
        if not enriched.content_hash:
            enriched = replace(spec, content_hash=content_hash_of(spec.text))
        if not enriched.chunk_policy:
            enriched = replace(enriched, chunk_policy=policy_for_category(spec.category).name)
        if not enriched.document_id:
            enriched = replace(enriched, document_id=spec.source_id)
        try:
            status = await upsert_knowledge_chunk(
                chunk_id=enriched.chunk_id,
                text=enriched.text,
                domain=enriched.domain,
                category=enriched.category,
                title=enriched.title,
                source_id=enriched.source_id,
                tags=list(enriched.tags),
                quality_tier=enriched.quality_tier,
                acl=enriched.acl,
                source_kind=enriched.source_kind,
                locale=enriched.locale,
                document_id=enriched.document_id,
                chunk_index=enriched.chunk_index,
                chunk_total=enriched.chunk_total,
                chunk_policy=enriched.chunk_policy,
                parent_chunk_id=enriched.parent_chunk_id,
                content_ptr=enriched.content_ptr,
                content_hash=enriched.content_hash,
                known_hashes=known_hashes,
            )
        except Exception as exc:  # noqa: BLE001 — 单条失败不阻断整批
            errors.append(f"{spec.chunk_id}: {type(exc).__name__}")
            skipped += 1
            continue
        if status == "upserted":
            upserted += 1
        elif status == "skipped":
            skipped += 1
        else:
            skipped += 1
            errors.append(f"{spec.chunk_id}: upsert returned error")
    return IngestResult(
        total=len(chunks),
        upserted=upserted,
        skipped=skipped,
        errors=tuple(errors),
    )


async def ingest_corpus_file(path: Path, *, dry_run: bool = False) -> IngestResult:
    chunks = load_corpus_file(path)
    return await ingest_corpus(chunks, dry_run=dry_run)


async def ingest_markdown_file(
    path: Path,
    *,
    document_id: str,
    domain: str,
    category: str,
    title: str,
    source_id: str,
    policy_name: str | None = None,
    dry_run: bool = False,
) -> IngestResult:
    text = path.read_text(encoding="utf-8")
    specs = specs_from_markdown(
        text,
        document_id=document_id,
        domain=domain,
        category=category,
        title=title,
        source_id=source_id,
        policy_name=policy_name,
        content_ptr=str(path.resolve()),
    )
    return await ingest_corpus(specs, dry_run=dry_run)
