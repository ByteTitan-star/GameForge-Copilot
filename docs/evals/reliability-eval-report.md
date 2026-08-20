# Reliability Mechanism Eval Report

## 1. Summary

Unit-style reliability checks on **10** scenarios. Pass rate: **100.0%**.

## 2. Methodology

- **Dataset**: `eval/datasets/reliability_faults.json` (10 entries)
- **Runner**: `eval/runners/reliability_eval.py`
- **Mode**: `unit_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `0e09085`
- **Date**: 2026-08-20

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| unit_pass_rate | 100.0% | >= 90% | ✅ |

## 4. Failure Analysis

All unit baseline cases passed.

## 6. Below-Target Items

All metrics meet production targets for this mode.

## 7. Conclusion

Live fault injection (timeout retry, checkpoint resume under kill) requires integration tests with worker + PostgreSQL.
