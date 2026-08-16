# ADR-01: Degraded Artifact Publishing

* Status: **Accepted**
* Date: 2026-08-15
* Related: P0 Reliability, `artifact_gate`

## Decision

`previewable` and `publishable` are distinct gates. A run may produce a degraded / previewable artifact without making it publishable.

## Consequences

* Promote / publish paths must consult artifact gate metadata.
* QA soft-fail or partial success must not silently become a public release.
