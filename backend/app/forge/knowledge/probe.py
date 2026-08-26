"""Knowledge RAG 运维联调：Embedding + Pinecone 连通性探测（ADR-14 §8）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.forge.knowledge.pinecone_store import knowledge_pinecone_configured
from app.llm.embeddings import embed_one, embedding_configured

_PROBE_VECTOR_ID = "__gameforge_connectivity_probe__"
_PROBE_TEXT = "GameForge knowledge connectivity probe 连通性探测"


@dataclass(frozen=True)
class KnowledgeProbeResult:
    ok: bool
    embedding_ok: bool
    pinecone_ok: bool
    vector_dim: int | None
    query_matches: int
    write_probe_ok: bool
    errors: tuple[str, ...]
    hints: tuple[str, ...]


def _config_hints() -> list[str]:
    hints: list[str] = []
    if not settings.embedding_enabled:
        hints.append("Set EMBEDDING_ENABLED=true")
    if not settings.embedding_apikey.strip():
        hints.append("Set EMBEDDING_APIKEY")
    if not settings.embedding_base_url.strip():
        hints.append(
            "Set EMBEDDING_BASE_URL (e.g. http://127.0.0.1:8080/v1 with compose embedding)"
        )
    if not settings.pinecone_enabled:
        hints.append("Set PINECONE_ENABLED=true")
    if not settings.pinecone_api_key.strip():
        hints.append("Set PINECONE_API_KEY")
    if not settings.pinecone_knowledge_host.strip():
        hints.append("Set PINECONE_KNOWLEDGE_HOST (gameforge-knowledge; not PINECONE_HOST)")
    return hints


async def _strict_pinecone_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    host = settings.pinecone_knowledge_host.strip().removeprefix("https://").removeprefix("http://")
    url = f"https://{host}/{path.lstrip('/')}"
    headers = {
        "Api-Key": settings.pinecone_api_key.strip(),
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}


async def probe_knowledge_stack(*, write_probe: bool = False) -> KnowledgeProbeResult:
    """探测 Embedding + Knowledge Index；write_probe 时写入并回读探针向量。"""
    errors: list[str] = []
    hints = _config_hints()

    if not embedding_configured():
        errors.append("embedding not configured")
    if not knowledge_pinecone_configured():
        errors.append("knowledge pinecone not configured (missing PINECONE_KNOWLEDGE_HOST?)")

    if errors:
        if not hints:
            hints = [
                "Create Pinecone index gameforge-knowledge (dim=512 for bge-small-zh-v1.5)",
                "Then: uv run python -m scripts.probe_knowledge_pinecone",
            ]
        return KnowledgeProbeResult(
            ok=False,
            embedding_ok=False,
            pinecone_ok=False,
            vector_dim=None,
            query_matches=0,
            write_probe_ok=False,
            errors=tuple(errors),
            hints=tuple(hints),
        )

    vector = await embed_one(_PROBE_TEXT)
    if vector is None:
        return KnowledgeProbeResult(
            ok=False,
            embedding_ok=False,
            pinecone_ok=False,
            vector_dim=None,
            query_matches=0,
            write_probe_ok=False,
            errors=("embedding request failed",),
            hints=tuple(hints or ["Check EMBEDDING_BASE_URL and TEI/embedding service"]),
        )

    namespace = settings.pinecone_knowledge_namespace or "global"
    query_matches = 0
    pinecone_ok = False
    write_probe_ok = False

    try:
        query_body: dict[str, Any] = {
            "namespace": namespace,
            "vector": vector,
            "topK": 3,
            "includeMetadata": True,
        }
        query_data = await _strict_pinecone_post("query", query_body)
        matches = query_data.get("matches")
        if isinstance(matches, list):
            query_matches = len(matches)
        pinecone_ok = True
    except httpx.HTTPError as exc:
        errors.append(f"pinecone query failed: {type(exc).__name__}")
        return KnowledgeProbeResult(
            ok=False,
            embedding_ok=True,
            pinecone_ok=False,
            vector_dim=len(vector),
            query_matches=0,
            write_probe_ok=False,
            errors=tuple(errors),
            hints=tuple(
                hints
                or [
                    "Verify PINECONE_KNOWLEDGE_HOST points to gameforge-knowledge index",
                    "Index dimension must match embedding model (512 for bge-small-zh-v1.5)",
                ]
            ),
        )

    if write_probe:
        try:
            upsert_body = {
                "namespace": namespace,
                "vectors": [
                    {
                        "id": _PROBE_VECTOR_ID,
                        "values": vector,
                        "metadata": {
                            "domain": "ops",
                            "category": "connectivity_probe",
                            "title": "connectivity probe",
                            "chunk_id": _PROBE_VECTOR_ID,
                            "source_id": "ops-probe",
                            "acl": "internal",
                            "text": _PROBE_TEXT[:500],
                            "created_at": int(time.time()),
                        },
                    }
                ],
            }
            upsert_data = await _strict_pinecone_post("vectors/upsert", upsert_body)
            upserted = upsert_data.get("upsertedCount")
            if upserted is not None and int(upserted) < 1:
                errors.append("pinecone upsert returned upsertedCount=0")
            else:
                read_data = await _strict_pinecone_post(
                    "query",
                    {
                        "namespace": namespace,
                        "vector": vector,
                        "topK": 5,
                        "includeMetadata": True,
                        "filter": {"chunk_id": _PROBE_VECTOR_ID},
                    },
                )
                matches = read_data.get("matches")
                if isinstance(matches, list):
                    write_probe_ok = any(
                        isinstance(m, dict) and str(m.get("id")) == _PROBE_VECTOR_ID
                        for m in matches
                    )
                if not write_probe_ok:
                    errors.append("probe vector not found after upsert")
        except httpx.HTTPError as exc:
            errors.append(f"pinecone upsert failed: {type(exc).__name__}")

    ok = pinecone_ok and not errors
    if write_probe:
        ok = ok and write_probe_ok

    return KnowledgeProbeResult(
        ok=ok,
        embedding_ok=True,
        pinecone_ok=pinecone_ok,
        vector_dim=len(vector),
        query_matches=query_matches,
        write_probe_ok=write_probe_ok if write_probe else pinecone_ok,
        errors=tuple(errors),
        hints=tuple(hints),
    )
