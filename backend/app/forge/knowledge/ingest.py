"""Curated Knowledge Ingestion（ADR-14 §3.5；Runtime Agent 禁止调用）。"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.forge.knowledge.pinecone_store import get_knowledge_pinecone_store
from app.llm.embeddings import embed_one


def _json_safe_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in meta.items():
        if isinstance(val, (str, int, float, bool)) or val is None:
            out[key] = val if val is not None else ""
        else:
            out[key] = json.dumps(val, ensure_ascii=False, default=str)
    return out


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
    vector = await embed_one(body)
    if vector is None:
        return False
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
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
    await store.upsert(
        vector_id=chunk_id,
        values=vector,
        metadata=_json_safe_meta(meta),
    )
    return True
