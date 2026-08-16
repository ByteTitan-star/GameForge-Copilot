# ADR-05: Recoverable Pause Representation

* Status: **Accepted**
* Date: 2026-08-15
* Related: P0 Reliability, HITL

## Decision

Recoverable pauses use explicit `paused` + `pause_reason` (and checkpoint metadata), not ad-hoc status strings alone.

## Consequences

* Resume / cancel / timeout paths share one pause model.
* Operators and clients can distinguish HITL wait vs infra pause.
