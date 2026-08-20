# Generation Success Rate Eval Report

## 1. Summary

Dataset validation: **50** prompts (15 simple / 20 medium / 15 hard). Live generation not executed.

## 2. Methodology

- **Dataset**: `eval/datasets/generation.json` (50 entries)
- **Runner**: `eval/runners/generation_eval.py`
- **Mode**: `offline_readiness`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `0e09085`
- **Date**: 2026-08-20

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| dataset_ready (>=50 prompts) | True | true | ✅ |
| success_rate | n/a (offline) | >= 90% | ⏳ |

## 7. Conclusion

Set EVAL_LIVE=1, EVAL_API_BASE_URL, EVAL_ACCESS_TOKEN then rerun with --live.

## 6. Below-Target Items

All metrics meet production targets for this mode.
