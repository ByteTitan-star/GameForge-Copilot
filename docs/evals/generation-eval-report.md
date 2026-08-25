# Generation Success Rate Eval Report

## 1. Summary

Live agent run on **2** prompts (`gen-001`–`gen-002` from `eval/datasets/generation.json`). Success rate: **100.0%** (2/2).

## 2. Methodology

- **Dataset**: `eval/datasets/generation.json` (50 entries)
- **Runner**: `eval/runners/generation_eval.py`
- **Mode**: `live_agent`
- **Reproduce**: `cd backend && uv run python -m eval.runners.generation_eval --live --limit 2`
- **Environment**: local API `http://127.0.0.1:8000`, worker + postgres/redis/rabbitmq via Docker
- **Git SHA**: `fb547ea`
- **Date**: 2026-08-25

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| success_rate | 100.0% | >= 90% | ✅ |
| prompts_run | 2 | — | — |

### Failure categories

- `ok`: 2

### Evaluated cases

| Case | Complexity | Prompt | Result | Wall (s) | HITL |
|------|------------|--------|--------|----------|------|
| `gen-001` | simple | Make a clicker game where clicking increases score | ✅ | 829.4 | 3 |
| `gen-002` | simple | Create a simple snake game with arrow keys | ✅ | 291.8 | 2 |

## 7. Conclusion

Local live generation gate passed at 100% success on subset `gen-001`–`gen-002`. CI main job uses `--limit 10` when `EVAL_API_BASE_URL` and `EVAL_ACCESS_TOKEN` secrets are configured.

## 6. Below-Target Items

All metrics meet production targets for this mode.
