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

## Daytona path (preferred when `DAYTONA_API_KEY` present)

```text
Worker
  → DaytonaSandbox.create  (requires sandbox_daytona_enabled=true + uv sync --extra daytona)
    → Daytona cloud sandbox (AsyncDaytona)
      ← source files / build commands uploaded
      → artifact bytes downloaded
    → DaytonaSandbox.destroy / HITL destroy_for_hitl (delete remote)
```

**Egress risk:** source, prompts-adjacent build inputs, and logs may leave the domestic
perimeter. Owner accepts Daytona egress for this project; keep Docker/local as fallback.

## HITL long wait

```text
active SandboxSession
  → destroy_for_hitl (explicit kill; no billing idle session)
  → checkpoint.sandbox_hitl metadata (includes tier)
  → user resumes
  → restore_sandbox_from_checkpoint / restore_after_hitl(tier=…)
     (fresh session; no mandatory snapshot)
```

Oneshoot CodeQa paths may skip explicit restore and simply `create` on next execute;
`restore_sandbox_from_checkpoint` exists for callers that hold a live session across HITL.
