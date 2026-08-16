# ADR-02: Preference Retention

* Status: **Proposed**（待 Accept；代码已按本草案 interim 行为落地）
* Date: 2026-08-16
* Related: P1 Memory Preferences

## Context

When a Game is deleted, Explicit vs Inferred preferences need different retention rules.

## Proposed Decision

1. **Explicit** preferences are **user-scoped** and **retained** when any Game is deleted.
2. **Inferred** preferences are user-scoped weak signals (`source=inferred`, lower confidence).
   * They **must not overwrite** an existing Explicit row for the same `(category, key)`.
   * Without a dedicated `evidence_game_id` column (not in MVP schema), deleting a Game
     does **not** auto-purge Inferred rows; use “clear my preferences” for full wipe.
3. **Clear my preferences** (`DELETE /me/preferences`) removes **all** rows for the user
   (Explicit + Inferred).

## Current implementation

* Explicit extract + API clear: shipped (P1).
* Inferred extract gated by `memory_preferences_inferred` (default **false**).

## Acceptance criteria to mark Accepted

* Product/legal sign-off on retention copy shown to users.
* Optional follow-up: add `evidence_game_id` / evidence list if Game-scoped purge is required.
