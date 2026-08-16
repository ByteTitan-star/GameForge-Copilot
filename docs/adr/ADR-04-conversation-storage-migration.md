# ADR-04: Conversation Storage Migration

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P1 Session Memory

## Context

Whether conversation history needs a parallel store (e.g. vector DB) or a schema migration away from `forge_messages`.

## Decision

1. **`forge_messages` remains the sole source of truth** for session turns.
2. Context injection stays via **ContextBuilder** (summary + recent turns + preferences + artifacts).
3. **No parallel conversation table** and **no Pinecone / vector conversation store** in production
   unless a follow-up ADR is opened.
4. Session Summary (`games.session_summary_json`) is a **derived cache**, not a second SoT.
5. Semantic Cache **shadow** may record Redis fingerprints for calibration; **direct semantic hit
   remains disabled** (Exact Cache on Redis is the production cache path).

## Consequences

* Preference / conversation vectors stay out of scope.
* Exact Cache (Redis whitelist) is the live cache; Semantic shadow ≠ hit cache.
