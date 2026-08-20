# User Preference Persistence Eval Report

## 1. Summary

Context injection baseline on **15** scenarios. Cross-session injection rate: **100.0%**.

## 2. Methodology

- **Dataset**: `eval/datasets/preference_scenarios.json` (15 entries)
- **Runner**: `eval/runners/preference_eval.py`
- **Mode**: `context_builder_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `118faea`
- **Date**: 2026-08-20

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| cross_session_injection_rate | 100.0% | 100% | ✅ |
| explicit_extraction_accuracy | 100.0% | >= 95% | ✅ |

## 7. Conclusion

Implicit extraction and DB persistence require live LLM + PostgreSQL. This baseline validates prompt injection formatting only.

## 6. Below-Target Items

All metrics meet production targets for this mode.
