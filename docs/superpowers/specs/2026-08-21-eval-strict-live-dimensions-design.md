# Eval Strict Live Dimensions Design

> Date: 2026-08-21
> Status: Approved
> Scope issues: `#116`, `#117`, `#118`, `#124`, `#125`
> Approach: **Route B** — shared telemetry foundation, then layered consumers
> Live subset default: **`--limit 10`** (`gen-001`…`gen-010`)

## 1. Purpose / Background

Remaining open eval issues still have offline scaffolds, but their acceptance criteria require true live / fault-injection / CI live generation behavior as specified in `docs/eval-framework-design.md`.

Closed related work already provides:

- `#115` live generation agent loop (`create game → run → auto-HITL → done`)
- `#119/#120` security eval + encoding fixes
- `#121` output audit quick_filter baseline
- `#122` guard → AuditLog persistence
- `#123` cross-model (verified locally, closed)

This design completes Dimensions 2, 4, 7, 8 and Phase-5 CI **without** duplicating five independent “full game factories”.

## 2. Goals and Non-Goals

### Goals

1. Enrich live generation telemetry once; derive `#116` / `#117` from it.
2. Implement live preference persistence eval (`#124`) via API + DB checks.
3. Implement reliability fault-injection eval (`#125`) with unit + live_fault modes.
4. Extend CI (`#118`) so `main` runs live generation with `--limit 10` and fails on regression.
5. Keep offline/unit baselines green for PR gates (no LLM required on PRs).

### Non-Goals

- Re-opening or re-implementing `#121`–`#123`.
- Changing production Forge graph semantics solely for eval convenience.
- Running full 50-prompt live suite on every PR (too slow/expensive).
- Building a separate multi-model live harness here (`#123` already closed).

## 3. Architecture (Route B)

```text
                    ┌──────────────────────────────┐
                    │ generation_eval --live       │
                    │ limit=10 (gen-001..010)      │
                    │ + messages + events harvest  │
                    └──────────────┬───────────────┘
                                   │ writes
                                   ▼
                    *_generation_eval.json (rich per_run)
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
         code_quality_eval   performance_eval    (dashboard)
         (#116 live_derived) (#117 phases/e2e)
                                   │
                     also: concurrency N=1,2,3
                     + sandbox/benchmark.py

Independent live runners (not piggybacked):
  preference_eval --live   (#124)
  reliability_eval --live-fault (#125)

CI:
  PR  → security quick_filter + offline_eval_gate
  main → offline gate + generation_eval --live --limit 10
```

### Design principles

- **DRY**: one live game loop owns HITL/polling; others consume JSON or dedicated APIs.
- **KISS**: prefer existing endpoints (`/runs/{id}`, `/messages`, `/events`, `/me/preferences`).
- **YAGNI**: no new microservice; no dashboard rewrite beyond `run_all.py` refresh.
- **Fail closed in CI**: missing secrets on `main` live job → job fails with clear message (not silent skip), unless explicitly documented `continue-on-error` for optional nightly jobs only.

## 4. Shared Foundation — Extend `generation_eval`

### 4.1 Default live subset

| Setting | Value |
|---------|-------|
| Default `--limit` | **10** |
| Dataset slice | first 10 entries of `eval/datasets/generation.json` (`gen-001`…`gen-010`) |
| CI `main` live | same `--limit 10` |
| Concurrency | keep `EVAL_CONCURRENCY` (default ≤ `MAX_CONCURRENT_RUNS`) |

### 4.2 Enriched `per_run` schema (additive)

Each live case result must include (in addition to existing fields):

```json
{
  "id": "gen-001",
  "success": true,
  "status": "done",
  "wall_clock_s": 381.2,
  "hitl_resolves": 2,
  "phases": [
    {"name": "plan", "duration_s": 12.4},
    {"name": "code", "duration_s": 90.1},
    {"name": "playtest", "duration_s": 20.0}
  ],
  "qa": {
    "attempts": 2,
    "first_pass": false,
    "final_pass": true,
    "repair_rounds": 1,
    "error_categories": ["runtime"]
  },
  "artifact": {
    "current_version": 1,
    "empty_or_trivial": false,
    "previewable": true
  }
}
```

### 4.3 Harvest sources

| Field | Source |
|-------|--------|
| `phases[]` | `GET /api/v1/runs/{run_id}/events` — aggregate `PHASE_CHANGE` (or equivalent phase markers) into durations |
| `qa.*` | run status + forge messages + code_qa attempt markers in events/messages |
| `artifact.*` | final `artifact_gate` + `GET /api/v1/games/{game_id}` (`current_version`) + HTML emptiness heuristic when content available |
| Failure category | diagnose / failed message text + `failure_kind` → mapped enum |

### 4.4 Error category mapping (`#116`)

Canonical set: `syntax` | `runtime` | `visual` | `timeout` | `infra` | `unknown`.

Mapping rules (first match wins) documented in runner helpers; unit-tested with fixture message strings.

## 5. Issue `#116` — Code Quality & QA Loop

### Modes (#116)

| Mode | When | What |
|------|------|------|
| `static_baseline` | default / CI offline | existing `code_quality_samples.json` structure/empty heuristics |
| `live_derived` | `EVAL_LIVE=1` or `--from-generation <json>` | metrics from enriched generation report |

### Metrics (live_derived)

| Metric | Target |
|--------|--------|
| `playtest_pass_rate` | ≥ 90% |
| `repair_effectiveness` | ≥ 70% |
| `avg_repair_rounds` | ≤ 2.0 |
| `max_repair_rounds` | ≤ `CODE_QA_MAX_ATTEMPTS` |
| `empty_output_rate` | ≤ 5% |
| `error_category_distribution` | tracked |

### Dataset changes

- Fix `code_quality_samples.json` labels and/or `_is_empty_output` heuristics so offline empty-detection accuracy meets ≥ 90% and sample empty rate interpretation is coherent (no contradictory “Below-Target: all meet” text).
- No new live prompt dataset; use generation subset of 10.

### Reports

- Refresh `docs/evals/code-quality-eval-report.md` with both modes when live data present.

## 6. Issue `#117` — Performance Benchmark

### Modes / stages

1. **Guard latency** (existing offline) — keep.
2. **Derived e2e + per-phase** from enriched generation JSON (`limit 10`).
3. **Concurrent throughput**: for `N ∈ {1,2,3}`, run the same 10-prompt subset (or a documented smaller fixed subset if 10×3 is too costly — **default: full 10 per N**, overridable via `EVAL_PERF_SUBSET_LIMIT`).
4. **Sandbox benchmark**: call `app.sandbox.benchmark.run_benchmark`; optional `DAYTONA_BENCHMARK_LIVE=1`.

### Metrics

| Metric | Target |
|--------|--------|
| `e2e_p50_latency_s` / `e2e_p95_latency_s` | tracked |
| `plan_latency_p50_s` / `code_gen_latency_p50_s` | tracked |
| `sandbox_exec_p95_ms` | ≤ 30000 |
| `concurrent_throughput` (runs/hour at N=1,2,3) | tracked |
| `latency_degradation_%` (p95 @ N=3 vs N=1) | tracked |

### Dataset

Optional small `eval/datasets/performance_subset.json` listing subset ids; default = first 10 generation ids.

## 7. Issue `#124` — Preference Persistence

### Dataset expansion (`preference_scenarios.json`)

Each scenario gains:

- `mode`: `explicit` | `implicit` | `conflict`
- `session1.messages[]` (or keep `session1_text` for backward compat)
- `expected_db[]` with `category`, `key`, `source`
- `session2_prompt`
- `expected_in_context[]`
- `conflict` block when `mode=conflict`
- `relevance_keywords[]` for optional post-generation checks

Requirements:

- ≥ 15 scenarios total
- include implicit and conflict cases
- conflict: newer explicit overrides older implicit → 100%

### Live runner flow

1. Create ephemeral user (register/verify/login) + ensure LLM config (reuse existing user config strategy / env keys).
2. Session 1: send preference signals (API path that triggers extract or explicit upsert).
3. `GET /api/v1/me/preferences` vs `expected_db`.
4. Session 2: create game/run with `session2_prompt`; verify preferences appear in context/messages.
5. Optional relevance: if run reaches playable artifact, check keywords (soft metric `preference_relevance` ≥ 85%).

### Modes (#124)

- `context_builder_baseline` (CI offline) — keep.
- `live_api` — full flow above.

## 8. Issue `#125` — Reliability Fault Injection

### Keep

- Existing `unit_baseline` cases and CI threshold on `unit_pass_rate`.

### Extend dataset types

| `type` | Injection | Success criteria |
|--------|-----------|------------------|
| `llm_timeout_then_ok` | mock/stub: fail first N LLM calls with timeout, then succeed | recovery ≥ 90% across cases |
| `mid_run_kill_resume` | stop worker mid-run → restart → retry/resume | checkpoint resume 100% |
| `oversized_continuation` | force truncated output path | continuation ≥ 85% |
| `all_fail_degradation` | all LLM fail | degradation/recoverable pause, no silent hang |
| `stale_cleanup` | stale running timeout path | cleanup 100% |

Prefer **test doubles / dev hooks** over brittle production-only behavior. Document any required `DEV_ROUTES_ENABLED` or eval-only flags.

### Modes (#125)

- `unit_baseline` — PR CI
- `live_fault` — manual / nightly / optional main (not required on every PR)

## 9. Issue `#118` — CI Eval Gate

### PR (`pull_request`)

- Keep: `security_eval` (quick_filter) + `offline_eval` gate.
- Do **not** run live LLM generation on every PR.

### Push to `main`

1. Offline gate (existing).
2. **Live generation**:
   `EVAL_LIVE=1 EVAL_API_BASE_URL=... EVAL_ACCESS_TOKEN=...`
   `python -m eval.runners.generation_eval --live --limit 10`
3. Fail if `success_rate < GENERATION_LIVE_SUCCESS_MIN` (default `0.90`).
4. Upload JSON + markdown reports as artifacts.
5. Optionally run `code_quality_eval` / `performance_eval` in `live_derived` mode against the just-produced generation JSON.

### Secrets / infra assumptions

Document required GitHub secrets and that a reachable API+worker environment must exist for the `main` live job (self-hosted runner or service containers). If the current repo cannot host full stack in GHA yet, the workflow must still encode the live job and fail loudly until infra is ready — **no silent placeholder success**.

## 10. Implementation Order

| Step | Deliverable | Verification |
|------|-------------|--------------|
| 1 | Enrich `generation_eval` harvest + schema | Live `--limit 10` JSON contains `phases`/`qa`/`artifact` |
| 2 | `#116` `live_derived` + fix offline empty samples | Report metrics + unit tests for category mapping |
| 3 | `#117` phases + concurrency + sandbox benchmark | Report includes N=1,2,3 and sandbox p95 |
| 4 | `#124` dataset + `live_api` | Targets met on local live run |
| 5 | `#125` fault dataset + `live_fault` | Unit still green; live_fault scenarios documented |
| 6 | `#118` main live job `--limit 10` | Workflow + secrets docs; dry-run where possible |
| 7 | `run_all.py` / dashboard refresh; close issues with English evidence comments | Dashboard reflects live dimensions |

## 11. File touch list (expected)

| Path | Role |
|------|------|
| `eval/runners/generation_eval.py` | Telemetry harvest |
| `eval/runners/code_quality_eval.py` | `live_derived` |
| `eval/runners/performance_eval.py` | phases, concurrency, sandbox |
| `eval/runners/preference_eval.py` | `live_api` |
| `eval/runners/reliability_eval.py` | `live_fault` |
| `eval/runners/_common.py` | shared JSON load helpers if needed |
| `eval/datasets/code_quality_samples.json` | offline empty accuracy fix |
| `eval/datasets/preference_scenarios.json` | implicit/conflict fields |
| `eval/datasets/reliability_faults.json` | fault injection cases |
| `eval/datasets/performance_subset.json` | optional |
| `.github/workflows/eval.yml` | main live `--limit 10` |
| `docs/evals/*-report.md` | refreshed reports |
| `docs/evals/dashboard.md` | orchestrator refresh |
| `eval/tests/*` | unit tests for parsers/mappers |

## 12. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Live `--limit 10` is slow/expensive on every main push | Keep on `main` only; allow `workflow_dispatch`; cache nothing sensitive |
| Phase/QA events schema drift | Centralize parsers + fixtures from real event samples |
| Preference LLM extract flaky | Prefer explicit upsert for conflict cases; soft-fail relevance with clear category |
| Mid-run kill flaky on Windows/CI | Gate `live_fault` to Linux CI or local documented procedure |
| Main live job lacks API stack | Explicit fail + README/setup; optional self-hosted runner follow-up |

## 13. Acceptance checklist (issue-level)

- [ ] `#116`: live QA metrics from generation telemetry; offline empty metrics fixed; report updated
- [ ] `#117`: per-phase + e2e percentiles; concurrency N=1,2,3; sandbox p95; degradation documented
- [ ] `#124`: ≥15 scenarios incl. implicit/conflict; live API accuracy targets met
- [ ] `#125`: unit + live_fault scenarios; recovery/resume/continuation/degradation rates meet targets
- [ ] `#118`: PR offline/security unchanged; `main` live generation `--limit 10` blocks on regression; artifacts uploaded

## 14. Resolved decisions

1. **Approach**: Route B (shared foundation) — **approved**.
2. **Live subset size** for CI / `#116` / `#117` derivation: **`--limit 10`** — **approved**.

## 15. Open questions (none blocking)

- Whether `#125` `live_fault` is required on every `main` push or nightly only: **default nightly / workflow_dispatch**; unit baseline remains on PR. Confirm during implementation plan if product wants it on main.
