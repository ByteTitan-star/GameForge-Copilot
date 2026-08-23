# Cross-Model Comparison Report

## 1. Summary

Comparison registry with **3** models and **10** fixed generation prompts.

## 2. Methodology

- **Dataset**: `eval/datasets/model_comparison.json` (10 entries)
- **Runner**: `eval/runners/model_comparison_eval.py`
- **Mode**: `offline_registry`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `cce0db2`
- **Date**: 2026-08-21

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Model | Provider | Prompts | Success Rate |
|-------|----------|---------|--------------|
| deepseek-v4-flash | openai_compat | 10 | n/a |
| qwen-max | openai_compat | 10 | n/a |
| glm-4-flash | openai_compat | 10 | n/a |

## 7. Conclusion

Live comparison: set EVAL_LIVE=1 and run generation_eval --live per model config.
