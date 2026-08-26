# Performance Benchmark Report

## 1. Summary

Guard quick_filter latency over **124** prompts: p50=0.782ms, p95=1.331ms.

## 2. Methodology

- **Dataset**: `adversarial.json + generation.json` (124 entries)
- **Runner**: `eval/runners/performance_eval.py`
- **Mode**: `live_concurrency`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `6e08d49`
- **Date**: 2026-08-25

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| guard_p50_ms | 0.782ms | documented | - |
| guard_p95_ms | 1.331ms | documented | - |
| guard_p99_ms | 1.756ms | documented | - |
| e2e_p50_s | 310.8 | tracked | - |
| e2e_p95_s | 310.8 | tracked | - |
| plan_latency_p50_s | n/a | tracked | - |
| code_gen_latency_p50_s | 93.955543 | tracked | - |
| sandbox_exec_p95_ms | 2.3303999987547286 | <= 30000 | - |
| latency_degradation_pct | 87.87 | tracked | - |

### 3.2 Concurrent throughput (N=1,2,3)

| N | prompts | success_rate | e2e_p95_s | throughput/h | wall_s |
|---|--------:|-------------:|----------:|-------------:|-------:|
| 1 | 2 | 1.0 | 310.8 | 7.4325 | 968.716 |
| 2 | 2 | 0.5 | 837.7 | 3.9847 | 903.466 |
| 3 | 2 | 0.5 | 583.9 | 3.9769 | 905.234 |

## 7. Conclusion

Guard latency always measured. Phase/e2e stats come from generation_eval JSON or live concurrency N=1. Sandbox p95 from local dry-run. Concurrency N=1,2,3 runs only with --concurrency-bench and live credentials.
