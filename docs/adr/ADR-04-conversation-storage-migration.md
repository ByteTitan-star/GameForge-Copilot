# ADR-04: Conversation Storage Migration

* Status: **Proposed**（继续以 `forge_messages` 为唯一 SoT）
* Date: 2026-08-16
* Related: P1 Session Memory

## Context

Whether conversation history needs a parallel store (e.g. vector DB) or a schema migration away from `forge_messages`.

## Proposed Decision

1. **`forge_messages` remains the sole source of truth** for session turns.
2. Context injection stays via **ContextBuilder** (summary + recent turns + preferences + artifacts).
3. **No parallel conversation table** and **no vector retrieval in production** until a follow-up ADR
   with retention, isolation (per-game/per-user), and cost model is Accepted.
4. Session Summary (`games.session_summary_json`) is a **derived cache**, not a second SoT.

## Consequences

* Offline / RAG experiments must stay behind flags and must not dual-write user history.
* Migrations that replace `forge_messages` require explicit cutover plan + backfill.
