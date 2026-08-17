# Daytona vs Docker Benchmark Checklist

Ops scorecard before flipping production `sandbox_backend`.

## Setup

1. `cd backend && uv sync --extra daytona`
2. Set `SANDBOX_DAYTONA_ENABLED=true`, `DAYTONA_API_KEY=...`, `SANDBOX_BACKEND=daytona`
3. **Dry-run (no Daytona, safe):** `uv run python scripts/sandbox_benchmark_dryrun.py --rounds 5`
4. **Live Daytona (opt-in):** `DAYTONA_BENCHMARK_LIVE=1 uv run python scripts/sandbox_benchmark_dryrun.py --rounds 3`

## Scorecard

| Metric | Docker | Daytona | Notes |
|--------|--------|---------|-------|
| Cold create p50 / p95 | | | |
| Execute (static HTML) p50 / p95 | | | |
| Cost per run | | | |
| Failure / timeout rate | | | |
| Data residency / egress OK? | | | Owner sign-off |

Do not set production `sandbox_backend=daytona` until ADR-03 is **Accepted** with this table filled
and ADR-11 §7 (session handle persistence) is satisfied.
