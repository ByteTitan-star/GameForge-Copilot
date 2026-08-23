# Performance Benchmark Report

## 1. Summary

Guard quick_filter latency over **124** prompts: p50=0.761ms, p95=1.446ms.

## 2. Methodology

- **Dataset**: `adversarial.json + generation.json` (124 entries)
- **Runner**: `eval/runners/performance_eval.py`
- **Mode**: `offline_guard_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `cce0db2`
- **Date**: 2026-08-21

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| guard_p50_ms | 0.761ms | documented | - |
| guard_p95_ms | 1.446ms | documented | - |
| guard_p99_ms | 1.664ms | documented | - |
| e2e_p50_s | n/a | tracked | - |
| e2e_p95_s | n/a | tracked | - |
| plan_latency_p50_s | n/a | tracked | - |
| code_gen_latency_p50_s | n/a | tracked | - |
| sandbox_exec_p95_ms | 5.865600000106497 | <= 30000 | - |

## 7. Conclusion

Guard latency always measured. Phase/e2e stats require enriched generation_eval JSON. Sandbox p95 from local dry-run benchmark. Concurrency N=1,2,3 is opt-in.
