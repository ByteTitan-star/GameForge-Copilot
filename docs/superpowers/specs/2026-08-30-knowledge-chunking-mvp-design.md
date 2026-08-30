# Design: Knowledge Production Chunking MVP (#146)

**Status:** Approved via user “继续” (option A)
**Date:** 2026-08-30

## Goal

Close #146 acceptance without S3/PostgreSQL two-tier storage.

## Scope (in)

- Chunk Policy Registry (subset of ADR-14 §3.6.3)
- `ChunkPlanner`: Markdown `##`/`###` split + oversized sliding split
- Pre-embed token guard ≤480 (`estimate_tokens`); never silent truncate
- Metadata: `document_id`, `chunk_index`, `chunk_total`, `chunk_policy`, `content_hash`, optional `content_ptr` (local path placeholder)
- Metadata `text` cap 2000 chars
- Idempotent skip on same `content_hash` (batch + InMemory scan; HTTP via metadata filter query when possible)
- Chunking eval helper: `truncation_rate` must be 0 after plan
- JSON curated corpus remains fast path (enrich metadata if missing)

## Scope (out)

- Real S3 / `knowledge_source` PostgreSQL
- Full boundary_precision human eval
- MMR / small-to-big runtime expand

## Interfaces

- `app/forge/knowledge/chunk_policy.py` — registry
- `app/forge/knowledge/chunk_planner.py` — `plan_markdown` / `plan_text` / `enrich_spec`
- `ingest.py` — token guard, hash skip, metadata fields
- `tests/forge/knowledge/test_chunk_planner.py`, `test_chunk_ingest.py`
