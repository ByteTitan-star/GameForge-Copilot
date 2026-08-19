# GameForge Eval Dashboard

> Last updated: 2026-08-19

## Current Status

| Dimension | Key Metric | Value | Target | Status | Evidence |
|-----------|------------|-------|--------|--------|----------|
| Security Guardrail | `block_rate` | 98.2% | >= 95% | ✅ | `docs/evals/security-eval-report.md` |
| Security Guardrail | `false_positive_rate` | 0.0% | <= 2% | ✅ | `docs/evals/security-eval-report.md` |
| Security Guardrail | `encoding_bypass_block_rate` | 94.7% | >= 90% | ✅ | `docs/evals/security-eval-report.md` |

## Iteration Summary

| Iteration | Change | block_rate | encoding_bypass_block_rate |
|-----------|--------|-----------:|---------------------------:|
| Baseline | Regex + lexicon only | 63.0% | 5.3% |
| Fix 1 | Add decode preprocessing; fix Chinese word boundary | 92.6% | 79.0% |
| Fix 2 | Lower base64 threshold; add Chinese jailbreak phrases | 96.3% | 89.5% |
| Fix 3 | Add HTML -> Unicode chained decode; fix dataset typo | 98.2% | 94.7% |

## Notes

- Raw machine-readable evidence is stored in `eval/reports/2026-08-19_security_eval.json`.
- Human-readable analysis is stored in `docs/evals/security-eval-report.md`.
- Remaining dimensions are still pending implementation and have not been evaluated yet.
