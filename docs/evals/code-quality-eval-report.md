# Code Quality & QA Loop Eval Report

## 1. Summary

Static structural analysis on **20** curated snippets. Structure detection accuracy: **100.0%**, empty-output detection: **100.0%**.

## 2. Methodology

- **Dataset**: `eval/datasets/code_quality_samples.json` (20 entries)
- **Runner**: `eval/runners/code_quality_eval.py`
- **Mode**: `static_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `cce0db2`
- **Date**: 2026-08-21

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| structure_detection_accuracy | 100.0% | >= 90% | ✅ |
| empty_output_detection_accuracy | 100.0% | >= 90% | ✅ |
| empty_labeled_rate (dataset) | 40.0% | informational | — |

## 4. Failure Analysis

No static baseline failures.

## 6. Below-Target Items

All metrics meet production targets for this mode.

## 7. Conclusion

Playtest pass rate and repair effectiveness require live generation runs (see generation_eval --live).
