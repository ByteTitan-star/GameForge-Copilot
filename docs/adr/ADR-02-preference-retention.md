# ADR-02: Preference Retention

> **【赶时间 · 偏好记忆第 0 步 · 约 8min】**
> Explicit 用户级保留；Inferred 不覆盖 Explicit；清偏好全删；active≤50。
> 读完去 `backend/app/forge/memory/__init__.py` 看完整文件顺序。

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P1 Memory Preferences

## Context

When a Game is deleted, Explicit vs Inferred preferences need different retention rules.
Active preferences are injected into ContextBuilder as durable user constraints.

## Decision

1. **Explicit** preferences are **user-scoped** and **retained** when any Game is deleted.
2. **Inferred** preferences are user-scoped weak signals (`source=inferred`).
   * They **must not overwrite** an existing Explicit row for the same `(category, key)`.
   * Deleting a Game does **not** auto-purge Inferred rows; use “clear my preferences” for full wipe.
3. **Clear my preferences** removes **all** rows for the user (Explicit + Inferred).
4. **Active cap = 50** (`memory_preferences_max_active`): overflow archives oldest Inferred first,
   then oldest Explicit. Preferences remain DB-backed (not a static file) and update dynamically.

## Consequences

* New sessions see ≤50 active preference constraints via ContextBuilder.
* Product copy for retention/clear remains Owner responsibility after Accept.
