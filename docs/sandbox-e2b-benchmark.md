# E2B vs Docker Benchmark Checklist

* Status: Template（未跑真实对照前不得据此切生产）
* Related: ADR-03

## How to run PoC (non-prod)

1. `cd backend && uv sync --extra e2b`
2. Set `SANDBOX_E2B_ENABLED=true`, `E2B_API_KEY=...`, `SANDBOX_BACKEND=e2b`
3. Prefer `E2B_ALLOW_INTERNET=false` unless the benchmark explicitly needs CDN fetch
4. **Dry-run (no E2B, safe):** `uv run python scripts/sandbox_benchmark_dryrun.py --rounds 5`
5. **Live E2B (opt-in):** `E2B_BENCHMARK_LIVE=1 uv run python scripts/sandbox_benchmark_dryrun.py --rounds 3`
6. Paste JSON metrics into the table below; keep Docker baseline on the same machine/workload

## Metrics table

| Metric | Docker | E2B | Notes |
| --- | --- | --- | --- |
| Cold start (p50/p95) | | | session create → ready |
| Build latency (p50/p95) | | | same fixture game |
| Cost per 100 runs | | | vendor invoice / estimate |
| Domestic network failure rate | | | timeouts / TLS |
| Data egress confirmed? | N/A (local) | Y/N | see sandbox-data-flow.md |

## Go / No-Go

Do not set production `sandbox_backend=e2b` until ADR-03 is **Accepted** with this table filled
and compliance review signed.
