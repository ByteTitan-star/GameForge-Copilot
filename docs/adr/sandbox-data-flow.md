# Sandbox Data Flow (ADR-03)

* Status: Reference for ADR-03 Proposed Go criteria
* Date: 2026-08-16

## Domestic production (DockerSandbox)

```text
Browser/API
  → Worker (forge graph)
    → DockerSandbox.create (local workspace dir)
      → docker run --network=none (sandbox image)
        → build/collect artifacts
      → DockerSandbox.destroy (rm workspace)
    → hosting store (object storage / local static)
  → User play URL
```

**Egress:** game source / prompts / UGC stay on self-hosted Worker + Docker host.
No third-party sandbox cloud.

## E2B PoC path (disabled by default)

```text
Worker
  → E2BSandbox.create  (requires sandbox_e2b_enabled=true + uv sync --extra e2b)
    → E2B cloud VM (AsyncSandbox)
      ← source files / build commands uploaded
      → artifact bytes downloaded
    → E2BSandbox.destroy / HITL destroy_for_hitl (kill remote)
```

**Egress risk:** source, prompts-adjacent build inputs, and logs may leave the domestic
perimeter. Do **not** enable for production until ADR-03 Go criteria are Accepted.

## HITL long wait

```text
active SandboxSession
  → destroy_for_hitl (explicit kill; no billing idle session)
  → checkpoint.sandbox_hitl metadata
  → user resumes
  → restore_after_hitl (create fresh session; no mandatory snapshot)
```
