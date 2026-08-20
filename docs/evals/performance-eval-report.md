# Performance Benchmark Report

## 1. Summary

Guard quick_filter latency over **124** prompts: p50=0.699ms, p95=1.315ms.

## 2. Methodology

- **Dataset**: `adversarial.json + generation.json` (124 entries)
- **Runner**: `eval/runners/performance_eval.py`
- **Mode**: `offline_guard_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `118faea`
- **Date**: 2026-08-20

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| guard_p50_ms | 0.699ms | documented | - |
| guard_p95_ms | 1.315ms | documented | - |
| guard_p99_ms | 1.653ms | documented | - |
| e2e_p50_s | n/a | tracked | - |
| e2e_p95_s | n/a | tracked | - |

## 7. Conclusion

Full performance benchmark (sandbox p95, concurrent throughput) requires generation_eval --live and sandbox benchmark integration.
