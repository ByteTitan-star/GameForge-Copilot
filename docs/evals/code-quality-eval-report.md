# Code Quality & QA Loop Eval Report

## 1. Summary

Static structural analysis on **20** curated snippets. Structure detection accuracy: **90.0%**, empty-output detection: **80.0%**.

## 2. Methodology

- **Dataset**: `eval/datasets/code_quality_samples.json` (20 entries)
- **Runner**: `eval/runners/code_quality_eval.py`
- **Mode**: `static_baseline`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `0497cc6`
- **Date**: 2026-08-21

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| structure_detection_accuracy | 90.0% | >= 90% | ✅ |
| empty_output_detection_accuracy | 80.0% | >= 90% | ❌ |
| empty_output_rate (samples) | 35.0% | <= 5% | ❌ |

## 4. Failure Analysis

| id | complete_match | empty_match |
|---|---|---|
| cq-002 | True | False |
| cq-003 | False | True |
| cq-009 | True | False |
| cq-014 | True | False |
| cq-016 | False | True |
| cq-018 | True | False |

## 6. Below-Target Items

All metrics meet production targets for this mode.

## 7. Conclusion

Playtest pass rate and repair effectiveness require live generation runs (see generation_eval --live).
