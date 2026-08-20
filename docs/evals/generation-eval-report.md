# Generation Success Rate Eval Report

## 1. Summary

Live agent run on **10** prompts (`gen-001`–`gen-010` from `eval/datasets/generation.json`). Success rate: **100.0%** (10/10).

## 2. Methodology

- **Dataset**: `eval/datasets/generation.json` (50 entries)
- **Runner**: `eval/runners/generation_eval.py`
- **Mode**: `live_agent`
- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`
- **Git SHA**: `53176a1`
- **Date**: 2026-08-20

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| success_rate | 100.0% | >= 90% | ✅ |
| prompts_run | 10 | — | — |

### Failure categories

- `ok`: 10

### Evaluated cases

| Case | Complexity | Prompt | Result | Wall (s) | HITL |
|------|------------|--------|--------|----------|------|
| `gen-001` | simple | Make a clicker game where clicking increases score | ✅ | 387.0 | 2 |
| `gen-002` | simple | Create a simple snake game with arrow keys | ✅ | 322.1 | 2 |
| `gen-003` | simple | Build a pong game with two paddles | ✅ | 321.8 | 2 |
| `gen-004` | simple | Make a memory card matching game with 8 cards | ✅ | 397.1 | 2 |
| `gen-005` | simple | Create a whack-a-mole style tapping game | ✅ | 331.8 | 2 |
| `gen-006` | simple | Build a color matching reaction game | ✅ | 477.9 | 2 |
| `gen-007` | simple | Make a simple platformer with jump and left/right | ✅ | 598.8 | 2 |
| `gen-008` | simple | Create a dodge falling objects survival game | ✅ | 568.5 | 2 |
| `gen-009` | simple | Build a typing speed mini game | ✅ | 276.5 | 2 |
| `gen-010` | simple | Make a coin collector side scroller | ✅ | 487.1 | 2 |

- Mean wall-clock: **416.9s** (min 276.5s / max 598.8s)

### Per-complexity

| Complexity | Run | Success | Rate |
|------------|-----|---------|------|
| simple | 10 | 10 | 100.0% |

## 7. Conclusion

Live agent evaluation complete (create game → run → auto-HITL → terminal status). Success = `done` and playable artifact (`generation_success` / `previewable` / `current_version >= 1`).

## 6. Below-Target Items

All metrics meet production targets for this mode.
