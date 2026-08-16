# ADR-03: Sandbox Provider Strategy

* Status: **Proposed**（生产默认仍为 Docker；E2B 仅 PoC）
* Date: 2026-08-16
* Related: P3 Sandbox

## Context

Choose production sandbox provider: Docker vs E2B (or hybrid), with domestic data-egress constraints.

## Proposed Decision

1. **Production default: `DockerSandbox`** (`sandbox_backend=docker`).
2. **E2B remains PoC-only** until Go criteria below are met; `sandbox_e2b_enabled` stays
   default **false**. Adapter may exist, but enabling it is not a production approval.
3. LocalSandbox remains the default for developer machines (`sandbox_backend=local`).
4. Hybrid (Docker domestic + E2B overseas) requires a **new** ADR amendment, not silent flag flips.

## Go criteria for E2B production (all required)

* Data-flow diagram reviewed (source/prompt/assets egress paths).
* Contract/DPA + retention policy acceptable.
* Domestic network latency/cost benchmark vs Docker recorded.
* Security review of UGC execution surface.

## No-Go default

Until Accepted with Go criteria checked: **do not** set E2B as production `sandbox_backend`.
