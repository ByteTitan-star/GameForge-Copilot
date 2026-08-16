# ADR-04: Conversation Storage Migration

* Status: **Pending**
* Date: 2026-08-15
* Related: P1 Session Memory

## Context

Whether `forge_messages` remains the sole source of truth or migrates to another store.

## Current interim

**`forge_messages` is the only SoT.** No parallel conversation table.

## Blocking

Vector retrieval / alternate SoT until this ADR is accepted.
