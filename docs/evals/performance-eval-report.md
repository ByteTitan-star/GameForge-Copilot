# Performance Benchmark Report

## 1. Summary

Guard quick_filter latency over **124** prompts: p50=0.793ms, p95=1.410ms. Live concurrency bench on **2** prompts at N=1,2,3: all **100%** success; latency degradation (p95 @ N=3 vs N=1) **-28.0%**.

## 2. Methodology

- **Dataset**: `adversarial.json + generation.json` + `performance_subset.json` (subset limit 2)
- **Runner**: `eval/runners/performance_eval.py --concurrency-bench`
- **Mode**: `live_concurrency`
- **Reproduce**: `EVAL_PERF_CONCURRENCY_BENCH=1 EVAL_PERF_SUBSET_LIMIT=2 uv run python -m eval.runners.performance_eval --concurrency-bench`
- **Environment**: local API `http://127.0.0.1:8000`
- **Git SHA**: `fb547ea`
- **Date**: 2026-08-25

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| guard_p50_ms | 0.793ms | documented | - |
| guard_p95_ms | 1.410ms | documented | - |
| guard_p99_ms | 1.935ms | documented | - |
| e2e_p50_s | 356.8 | tracked | - |
| e2e_p95_s | 356.8 | tracked | - |
| plan_latency_p50_s | 64.27 | tracked | - |
| code_gen_latency_p50_s | 101.05 | tracked | - |
| sandbox_exec_p95_ms | 6.86 | <= 30000 | ✅ |
| latency_degradation_pct | -28.03 | tracked | - |

### 3.2 Concurrent throughput (N=1,2,3)

| N | prompts | success_rate | e2e_p95_s | throughput/h | wall_s |
|---|--------:|-------------:|----------:|-------------:|-------:|
| 1 | 2 | 1.0 | 356.8 | 8.82 | 815.9 |
| 2 | 2 | 1.0 | 381.3 | 11.93 | 603.5 |
| 3 | 2 | 1.0 | 256.8 | 18.74 | 384.2 |

## 7. Conclusion

Per-phase latency, sandbox dry-run p95, and N=1/2/3 concurrency throughput documented from local live runs. Negative degradation indicates faster p95 at N=3 on this small subset (variance; not a production SLO claim).
