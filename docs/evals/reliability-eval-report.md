# Reliability Mechanism Eval Report

## 1. Summary

Reliability checks on **10** scenarios (mode=unit_baseline).

## 2. Methodology

- **Dataset**: `eval/datasets/reliability_faults.json` (10 entries)
- **Runner**: `eval/runners/reliability_eval.py`
- **Mode**: `unit_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `fb547ea`
- **Date**: 2026-08-25

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| unit_pass_rate | 100.0% | >= 90% | ✅ |

## 4. Failure Analysis

All evaluated cases passed.

## 6. Below-Target Items

All metrics meet production targets for this mode.

## 7. Conclusion

Unit baseline only. Run with --live-fault for simulated fault-injection metrics.
