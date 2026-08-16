# ADR-03: Sandbox Provider Strategy

* Status: **Pending**
* Date: 2026-08-15
* Related: P3 Sandbox

## Context

E2B vs Docker for production isolation, including domestic data-egress / compliance.

## Current interim

* Production default: DockerSandbox (or LocalSandbox for dev)
* E2B: PoC only, gated by `sandbox_e2b_enabled=false`

## Go condition (non-exhaustive)

Data-flow confirmation, egress policy, DPA/compliance, domestic network benchmarks.
