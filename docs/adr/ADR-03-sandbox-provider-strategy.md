# ADR-03: Sandbox Provider Strategy

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: [sandbox-data-flow.md](./sandbox-data-flow.md), [../sandbox-e2b-benchmark.md](../sandbox-e2b-benchmark.md)

## Context

Choose sandbox provider for isolated game build/execute: Docker vs E2B (or hybrid).

## Decision

1. **Preferred backend: E2B** (`sandbox_backend=e2b`, `sandbox_e2b_enabled=true`).
2. **Secret**: `E2B_API_KEY` must come from environment / secret store — never committed.
3. **Fallback**: if E2B is selected but key missing / disabled, factory falls back to
   `docker`, then `local` so developer machines and CI do not hard-fail.
4. **Tier auto**: `sandbox_tier_auto=true` picks `lite|standard|heavy` from engine/size/telemetry;
   base tier remains `sandbox_default_tier=standard`.
5. Network: `e2b_allow_internet=false` by default.

## Consequences

* Production-like runs should set a real `E2B_API_KEY`.
* Benchmark table in `sandbox-e2b-benchmark.md` remains the ops scorecard for cost/latency.
* Data egress via E2B is accepted by Owner for this project configuration.
