# GameForge Eval Dashboard

> Last orchestrator run: 2026-08-21T15:41:06Z | Git SHA: `cce0db2`

| Dimension | Value | Target | Status |
|-----------|-------|--------|--------|
| Generation Success | offline | >= 90% | ⏳ |
| Code Quality | 100.0% | >= 90% | ✅ |
| Security Guardrail | 100.0% | >= 95% | ✅ |
| Performance | 1.446ms | documented | ✅ |
| Output Audit | 95.0% | >= 90% | ✅ |
| Model Comparison | offline_registry | - | ✅ |
| Preference Persistence | 100.0% | 100% | ✅ |
| Reliability | 100.0% | >= 90% | ✅ |

## Issue Coverage

| Issue | Runner |
|-------|--------|
| #115 | `eval/runners/generation_eval.py` |
| #116 | `eval/runners/code_quality_eval.py` |
| #119 | `eval/runners/security_eval.py` |
| #117 | `eval/runners/performance_eval.py` |
| #121 | `eval/runners/output_audit_eval.py` |
| #123 | `eval/runners/model_comparison_eval.py` |
| #124 | `eval/runners/preference_eval.py` |
| #125 | `eval/runners/reliability_eval.py` |

## Notes

- #118 CI gate: `.github/workflows/eval.yml` (PR security+offline; main live generation `--limit 10`)
- #122 AuditLog persistence: verified via `backend/scripts/verify_guard_auditlog_persistence.py`
- Live generation: `EVAL_LIVE=1` + `EVAL_API_BASE_URL` + `EVAL_ACCESS_TOKEN`
- Preference live API: `EVAL_PREF_LIVE=1` (separate from generation EVAL_LIVE)
- Reliability fault sims: `EVAL_LIVE_FAULT=1` or workflow_dispatch `run_live_fault=true`
