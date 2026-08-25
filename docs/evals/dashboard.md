# GameForge Eval Dashboard

> Last orchestrator run: 2026-08-25T06:13:24Z | Git SHA: `fb547ea` | Local live verified 2026-08-25

| Dimension | Value | Target | Status |
|-----------|-------|--------|--------|
| Generation Success | 100.0% (live n=2) | >= 90% | ✅ |
| Code Quality | 100.0% | >= 90% | ✅ |
| Security Guardrail | 100.0% | >= 95% | ✅ |
| Performance | N=1/2/3 live bench | documented | ✅ |
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
- Live generation: `EVAL_LIVE=1` + `EVAL_API_BASE_URL` + `EVAL_ACCESS_TOKEN` (local verified 2026-08-25; main CI needs repo secrets)
- Performance concurrency (#117): `EVAL_PERF_CONCURRENCY_BENCH=1` + live credentials; optional `EVAL_PERF_SUBSET_LIMIT`
- Preference live API: `EVAL_PREF_LIVE=1` (separate from generation EVAL_LIVE)
- Reliability fault sims: `EVAL_LIVE_FAULT=1` or workflow_dispatch `run_live_fault=true`
