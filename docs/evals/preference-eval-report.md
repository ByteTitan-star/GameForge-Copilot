# User Preference Persistence Eval Report

## 1. Summary

Preference eval on **17** scenarios (mode=context_builder_baseline).

## 2. Methodology

- **Dataset**: `eval/datasets/preference_scenarios.json` (17 entries)
- **Runner**: `eval/runners/preference_eval.py`
- **Mode**: `context_builder_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `cce0db2`
- **Date**: 2026-08-21

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| cross_session_injection_rate | 100.0% | 100% | ✅ |
| explicit_extraction_accuracy | 100.0% | >= 95% | ✅ |

## 7. Conclusion

Baseline validates ContextBuilder injection formatting. Use --live for API/DB persistence checks.

## 6. Below-Target Items

All metrics meet production targets for this mode.
