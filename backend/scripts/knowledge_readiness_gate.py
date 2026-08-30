"""Knowledge RAG Production Readiness Gate checker (#147 follow-up).

Does NOT enable KNOWLEDGE_RAG_ENABLED. Prints pass/fail checklist for ops.
Exit 0 only when all hard checks pass (soft warnings still exit 0 with WARN lines).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from app.core.config import settings
from app.forge.knowledge.pinecone_store import knowledge_pinecone_configured
from app.llm.embeddings import embedding_configured


@dataclass(frozen=True)
class GateItem:
    name: str
    ok: bool
    detail: str
    hard: bool = True


def collect_gate_items() -> list[GateItem]:
    items: list[GateItem] = []
    items.append(
        GateItem(
            name="default_flag_off",
            ok=settings.knowledge_rag_enabled is False,
            detail=(
                "KNOWLEDGE_RAG_ENABLED is false (safe default)"
                if not settings.knowledge_rag_enabled
                else "KNOWLEDGE_RAG_ENABLED is TRUE — confirm ops approval before prod"
            ),
            hard=False,
        )
    )
    items.append(
        GateItem(
            name="pinecone_knowledge_host",
            ok=knowledge_pinecone_configured(),
            detail=(
                "PINECONE_KNOWLEDGE_HOST configured"
                if knowledge_pinecone_configured()
                else "missing PINECONE_KNOWLEDGE_HOST / API key / pinecone_enabled"
            ),
        )
    )
    items.append(
        GateItem(
            name="embedding",
            ok=embedding_configured(),
            detail=(
                "embedding client configured"
                if embedding_configured()
                else "embedding not configured (EMBEDDING_*)"
            ),
        )
    )
    dim_ok = int(settings.knowledge_embedding_expected_dim) > 0
    items.append(
        GateItem(
            name="embedding_dim_contract",
            ok=dim_ok,
            detail=(
                f"knowledge_embedding_expected_dim={settings.knowledge_embedding_expected_dim}"
                if dim_ok
                else "set KNOWLEDGE_EMBEDDING_EXPECTED_DIM (e.g. 512)"
            ),
        )
    )
    model_ok = bool(settings.knowledge_embedding_expected_model.strip())
    items.append(
        GateItem(
            name="embedding_model_contract",
            ok=model_ok,
            detail=(
                f"expected_model={settings.knowledge_embedding_expected_model!r}"
                if model_ok
                else "set KNOWLEDGE_EMBEDDING_EXPECTED_MODEL"
            ),
        )
    )
    ver_ok = bool(settings.knowledge_embedding_version.strip())
    items.append(
        GateItem(
            name="embedding_version",
            ok=ver_ok,
            detail=(
                f"version={settings.knowledge_embedding_version!r}"
                if ver_ok
                else "set KNOWLEDGE_EMBEDDING_VERSION for stale-vector skip"
            ),
            hard=False,
        )
    )
    items.append(
        GateItem(
            name="circuit_enabled",
            ok=bool(settings.knowledge_circuit_enabled),
            detail="knowledge circuit breaker enabled",
            hard=False,
        )
    )
    items.append(
        GateItem(
            name="metadata_validation",
            ok=bool(settings.knowledge_metadata_validation_enabled),
            detail="metadata taxonomy validation enabled",
            hard=False,
        )
    )
    root = settings.knowledge_source_root.strip()
    items.append(
        GateItem(
            name="source_archive_root",
            ok=bool(root),
            detail=f"KNOWLEDGE_SOURCE_ROOT={root!r}",
            hard=False,
        )
    )
    backend = (settings.knowledge_source_backend or "local").strip().lower()
    items.append(
        GateItem(
            name="source_backend",
            ok=backend in {"local", "s3"},
            detail=f"KNOWLEDGE_SOURCE_BACKEND={backend!r}",
            hard=True,
        )
    )
    if backend == "s3":
        s3_ok = bool(
            settings.s3_bucket.strip()
            and settings.s3_ak.strip()
            and settings.s3_sk.strip()
            and settings.s3_endpoint.strip()
            and settings.s3_region.strip()
        )
        items.append(
            GateItem(
                name="source_s3_credentials",
                ok=s3_ok,
                detail=(
                    "S3_* configured for knowledge archive"
                    if s3_ok
                    else "knowledge_source_backend=s3 requires S3_BUCKET/AK/SK/ENDPOINT/REGION"
                ),
            )
        )
    return items


def main() -> int:
    items = collect_gate_items()
    hard_fail = 0
    for item in items:
        mark = "PASS" if item.ok else ("FAIL" if item.hard else "WARN")
        if item.hard and not item.ok:
            hard_fail += 1
        print(f"[{mark}] {item.name}: {item.detail}")
    print()
    if hard_fail:
        print(f"Gate NOT ready: {hard_fail} hard failure(s).")
        print("Do not set KNOWLEDGE_RAG_ENABLED=true until hard checks pass.")
        return 1
    print("Hard checks passed. Soft warnings above (if any) should be reviewed.")
    print("Enabling RAG in production still requires explicit ops approval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
