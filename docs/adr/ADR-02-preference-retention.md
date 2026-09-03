# ADR-02: Preference Retention

> **Status: Deprecated（已废弃）**
> **Superseded by:** [ADR-15: Preference Memory（As-Is）](./ADR-15-preference-memory-as-is.md)
> **Deprecated-on:** 2026-09-02
> 本文仅作历史存档；**不得**再作为实现或评审依据。偏好保留 / Explicit·Inferred / active 上限等决策以 ADR-15 为准。

---

* Former status: Accepted（2026-08-16）
* Accepted-by: ByteTitan-star
* Related: P1 Memory Preferences → 现见 ADR-15

## Context（历史）

When a Game is deleted, Explicit vs Inferred preferences need different retention rules.
Active preferences are injected into ContextBuilder as durable user constraints.

## Decision（历史摘要；已迁移至 ADR-15）

1. **Explicit** preferences are **user-scoped** and **retained** when any Game is deleted.
2. **Inferred** preferences are user-scoped weak signals (`source=inferred`).
   * They **must not overwrite** an existing Explicit row for the same `(category, key)`.
   * Deleting a Game does **not** auto-purge Inferred rows; use “clear my preferences” for full wipe.
3. **Clear my preferences** removes **all** rows for the user (Explicit + Inferred).
4. **Active cap = 50** (`memory_preferences_max_active`): overflow archives oldest Inferred first,
   then oldest Explicit. Preferences remain DB-backed (not a static file) and update dynamically.

## Consequences（历史）

* 详见 ADR-15。目标态 redesign 见 Issue #162。
