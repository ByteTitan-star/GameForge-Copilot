# User Preference Persistence Eval Report

## 1. Summary

Preference eval on **8** scenarios (mode=live_api).

## 2. Methodology

- **Dataset**: `eval/datasets/preference_scenarios.json` (8 entries)
- **Runner**: `eval/runners/preference_eval.py`
- **Mode**: `live_api`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `571648f`
- **Date**: 2026-08-21

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| db_match_rate | 100.0% | >= 95% | ✅ |
| cross_session_injection_rate | 100.0% | 100% | ✅ |
| preference_conflict_resolution | 100.0% | 100% | ✅ |

## 7. Conclusion

Live API preference persistence against running backend + PostgreSQL.

## 6. Below-Target Items

All metrics meet production targets for this mode.
