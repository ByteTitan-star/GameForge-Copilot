# GameForge Evaluation Framework Design

> Comprehensive evaluation system covering Agent pipeline quality, security
> guardrails, reliability mechanisms, and performance benchmarks.
> Every eval dimension produces a **persistent markdown report** in
> `docs/evals/` that can be directly used for analysis and presentation.

---

## Table of Contents

1. [Goals & Principles](#1-goals--principles)
2. [Architecture Overview](#2-architecture-overview)
3. [Eval Dimensions](#3-eval-dimensions)
4. [Test Dataset](#4-test-dataset)
5. [Report Specification](#5-report-specification)
6. [Below-Target Workflow](#6-below-target-workflow)
7. [Implementation Plan](#7-implementation-plan)

---

## 1. Goals & Principles

### Goals

- Quantify the claim "game generation success rate improved from ~30% to 90%"
  with reproducible evidence.
- Establish regression gates: any change that degrades key metrics blocks merge.
- Provide a structured improvement loop: **baseline → identify gap → fix →
  retest → document delta**.
- Produce **presentation-ready reports** in `docs/evals/` for each dimension.

### Principles

- **Reproducibility**: fixed seed prompts, pinned model versions, deterministic
  where possible.
- **Data-driven**: every eval run produces a timestamped JSON report; markdown
  reports in `docs/evals/` summarise trends across runs.
- **Incremental**: each dimension can run independently; full suite is optional.
- **Real execution**: evals hit real LLM APIs and real sandboxes (not mocks)
  for the metrics that matter.
- **Gate before ship**: any metric below production target MUST be fixed before
  merge. Optimisation plan must be aligned with the user before implementation.

---

## 2. Architecture Overview

```text
eval/
├── datasets/                       # Curated prompt datasets (JSON)
│   ├── generation.json             # 50+ game generation prompts
│   ├── adversarial.json            # 50+ attacks + 20 legitimate
│   ├── edge_cases.json             # 15+ malformed / ambiguous / multilingual
│   ├── output_violations.json      # 20+ violations + 20 clean
│   ├── preference_scenarios.json   # 15+ cross-session preference cases
│   └── reliability_faults.json     # 10+ fault injection scenarios
├── runners/                        # Eval runner scripts
│   ├── generation_eval.py          # Dim-1: end-to-end generation success
│   ├── code_quality_eval.py        # Dim-2: code quality & QA loop
│   ├── security_eval.py            # Dim-3: guardrail effectiveness
│   ├── performance_eval.py         # Dim-4: latency & throughput
│   ├── output_audit_eval.py        # Dim-5: output audit coverage
│   ├── model_comparison_eval.py    # Dim-6: cross-model comparison
│   ├── preference_eval.py          # Dim-7: preference persistence
│   └── reliability_eval.py         # Dim-8: reliability mechanisms
├── reports/                        # Raw JSON reports (gitignored, CI artifacts)
│   └── 2026-08-20_generation_eval.json
├── conftest.py                     # Shared fixtures (API client, auth, cleanup)
└── run_all.py                      # Orchestrator: run all dims, merge reports

docs/evals/                         # FINAL REPORTS — presentation-ready markdown
├── dashboard.md                    # Summary dashboard across all dimensions
├── generation-eval-report.md       # Dim-1 report
├── code-quality-eval-report.md     # Dim-2 report
├── security-eval-report.md         # Dim-3 report
├── performance-eval-report.md      # Dim-4 report
├── output-audit-eval-report.md     # Dim-5 report
├── model-comparison-report.md      # Dim-6 report
├── preference-eval-report.md       # Dim-7 report
└── reliability-eval-report.md      # Dim-8 report
```

**Key rule**: `eval/reports/` stores raw JSON (gitignored). `docs/evals/` stores
human-readable markdown reports (committed). After every eval run, the runner
MUST update the corresponding `docs/evals/*.md` file.

---

## 3. Eval Dimensions

### Dimension 1: Generation Success Rate

**What**: end-to-end game generation from natural language prompt to playable
artifact.

| Metric | Definition | Target |
|--------|-----------|--------|
| `success_rate` | Runs with `status=done` + playable artifact / total | ≥ 90% |
| `plan_success_rate` | Runs producing valid plan JSON | ≥ 95% |
| `code_gen_success_rate` | Initial code generation producing parseable HTML/JS | ≥ 85% |
| `qa_pass_first_attempt` | CodeQaLoop passes on first attempt | tracked |
| `avg_qa_rounds` | Average repair rounds before pass | tracked |
| `failure_categories` | Breakdown: timeout / parse error / sandbox crash / QA exhausted | tracked |
| `avg_wall_clock_s` | Average end-to-end wall-clock time | tracked |
| `avg_token_usage` | Average total tokens consumed per run | tracked |

**Method**:

1. Load `datasets/generation.json` (50+ prompts, tagged: simple / medium /
   hard).
2. For each prompt, call forge API to create game and start run.
3. Poll until `status ∈ {done, failed}` or timeout (default 15 min).
4. Classify: success (done + artifact) / failure (with category).
5. Collect per-run: wall-clock, token usage (WS `LLM_CALL` events), QA
   rounds, final status, phase timestamps.

**Dataset** (generation.json): minimum 50 prompts — 15 simple, 20 medium,
15 hard. Each entry:

```json
{
  "id": "gen-001",
  "prompt": "Make a simple clicking game where score increases on click",
  "complexity": "simple",
  "expected_elements": ["click handler", "score display", "incrementing logic"],
  "tags": ["casual", "minimal"]
}
```

### Dimension 2: Code Quality & QA Loop Effectiveness

**What**: quality of LLM-generated code and self-repair loop effectiveness.

| Metric | Definition | Target |
|--------|-----------|--------|
| `playtest_pass_rate` | Playwright smoke tests passing (final) | ≥ 90% |
| `repair_effectiveness` | Failed runs fixed by QA loop / failed first attempts | ≥ 70% |
| `avg_repair_rounds` | Mean rounds to reach pass | ≤ 2.0 |
| `max_repair_rounds` | Worst case | ≤ CODE_QA_MAX_ATTEMPTS |
| `empty_output_rate` | Runs producing empty or trivially broken HTML | ≤ 5% |
| `error_category_distribution` | Syntax / runtime / visual / timeout breakdown | tracked |

**Method**: piggybacks on Dimension 1 runs. Extract from WS events and run
messages:

- First `code_or_repair` → `playtest` result.
- Number of diagnose → repair cycles.
- Final `PlaytestResult.ok`.
- If failed: diagnose error category.

### Dimension 3: Security Guardrail Effectiveness

**What**: adversarial prompt injection and encoding bypass resistance.

| Metric | Definition | Target |
|--------|-----------|--------|
| `block_rate` | Adversarial correctly blocked / total adversarial | ≥ 95% |
| `false_positive_rate` | Legitimate incorrectly blocked / total legitimate | ≤ 2% |
| `encoding_bypass_block_rate` | Encoded attacks blocked (base64/HTML/Unicode/rot13) | ≥ 90% |
| `regex_quick_filter_hit_rate` | Caught by regex layer | tracked |
| `lexicon_hit_rate` | Caught by lexicon layer | tracked |
| `llm_audit_hit_rate` | Caught only by LLM audit | tracked |
| `avg_guard_latency_ms` | Average guard check time | tracked |

**Method**:

1. Load `datasets/adversarial.json` — 50+ adversarial + 20 legitimate.
2. Call `Guard.check()` directly. Record verdict, catching layer, latency.
3. Compute all metrics. If `encoding_bypass_block_rate` < 90% → trigger
   encoding countermeasure implementation → retest → document delta.

**Dataset** (adversarial.json):

- **Direct attacks**: jailbreak, prompt injection, malicious code, system
  prompt extraction.
- **Encoded attacks**: same payloads in base64, HTML entity, Unicode escape,
  rot13, mixed encoding.
- **Legitimate prompts**: normal game requests for false-positive measurement.
- Each entry specifies `encoding`, `attack_type`, `expected_verdict`.

### Dimension 4: Performance Benchmark

**What**: latency distribution and throughput under load.

| Metric | Definition | Target |
|--------|-----------|--------|
| `e2e_p50_latency_s` | Median end-to-end time | tracked |
| `e2e_p95_latency_s` | 95th percentile e2e time | tracked |
| `plan_latency_p50_s` | Plan phase median | tracked |
| `code_gen_latency_p50_s` | Code gen phase median | tracked |
| `sandbox_exec_p95_ms` | Sandbox create+exec p95 | ≤ 30s |
| `concurrent_throughput` | Successful runs/hour at N=1,2,3 | tracked |
| `latency_degradation_%` | p95 at N=3 vs N=1 | tracked |

**Method**:

1. Collect per-phase timing from WS `PHASE_CHANGE` events during Dim-1 runs.
2. Concurrent test: launch N=1,2,3 simultaneous runs, measure completion
   rate and latency degradation.
3. Integrate `sandbox/benchmark.py` results.

### Dimension 5: Output Audit Coverage

**What**: output-side content moderation on LLM-generated code.

| Metric | Definition | Target |
|--------|-----------|--------|
| `violation_detection_rate` | Injected violations caught | ≥ 90% |
| `false_positive_rate` | Clean outputs incorrectly flagged | ≤ 3% |
| `audit_latency_p95_ms` | Output audit p95 response time | ≤ 500ms |
| `violation_type_breakdown` | Detection rate per type (XSS / offensive / exfil) | tracked |

**Method**:

1. Load `datasets/output_violations.json` — 20+ violations + 20 clean.
2. Feed through `Guard.check(side="output")`.
3. Measure accuracy and latency.

### Dimension 6: Cross-Model Comparison

**What**: same eval dataset across different LLM providers to guide model
selection.

| Metric | Definition | Per-Model |
|--------|-----------|-----------|
| `success_rate` | Same as Dim-1 | per model |
| `avg_token_usage` | Total tokens consumed | per model |
| `avg_wall_clock_s` | End-to-end time | per model |
| `avg_cost_usd` | Estimated cost (token price × usage) | per model |
| `qa_pass_first_attempt` | First-attempt pass rate | per model |
| `failure_categories` | Failure distribution | per model |

**Method**:

1. Select a **fixed subset** of `datasets/generation.json` (10 prompts,
   balanced complexity).
2. For each model (DeepSeek-V4, Qwen-Max, GLM-4, GPT-4o, etc.), run the
   subset.
3. Cross-tabulate all Dim-1/Dim-2 metrics per model.
4. Compute cost estimates using public pricing.

**Report output**: comparison table + radar chart data for
quality / speed / cost / reliability axes.

### Dimension 7: User Preference Persistence

**What**: verify that the dual-channel preference extraction and cross-session
injection works correctly.

| Metric | Definition | Target |
|--------|-----------|--------|
| `explicit_extraction_accuracy` | Explicitly stated preferences correctly stored | ≥ 95% |
| `implicit_extraction_accuracy` | Post-conversation inferred preferences correct | ≥ 80% |
| `cross_session_injection_rate` | Preferences correctly loaded in new session | 100% |
| `preference_conflict_resolution` | Newer explicit overrides older implicit | 100% |
| `preference_relevance` | Generated game reflects loaded preferences | ≥ 85% |

**Method**:

1. Load `datasets/preference_scenarios.json` — 15+ scenarios, each with:
   - Session 1: conversation with explicit/implicit preference signals.
   - Expected preference records in DB.
   - Session 2: new conversation, verify preferences injected into system
     prompt, verify generated output reflects preferences.
2. Automate via API: create user → session 1 conversation → check DB →
   session 2 conversation → validate output.

### Dimension 8: Reliability Mechanism Effectiveness

**What**: verify timeout-retry, degradation fallback, circuit breaker,
checkpoint-resume under fault conditions.

| Metric | Definition | Target |
|--------|-----------|--------|
| `timeout_retry_recovery_rate` | Tasks recovering after LLM timeout + retry | ≥ 90% |
| `checkpoint_resume_success_rate` | Tasks resuming correctly from checkpoint | 100% |
| `degradation_fallback_triggers` | Fallback activates when primary path fails | 100% |
| `stale_task_cleanup_rate` | Stuck tasks correctly cleaned up | 100% |
| `continuation_success_rate` | Truncated output correctly continued | ≥ 85% |

**Method**:

1. Load `datasets/reliability_faults.json` — fault injection scenarios:
   - LLM API timeout simulation (mock 504 on first N calls, then succeed).
   - Mid-run process kill → restart → verify checkpoint resume.
   - Oversized LLM output → verify truncation + continuation.
   - All LLM calls fail → verify degradation/fallback behaviour.
2. Some scenarios require mock/stub LLM responses; others use real API
   with artificial delays.

---

## 4. Test Dataset

### Dataset Management

- All datasets live in `eval/datasets/` as JSON files.
- Each entry has a unique `id`, metadata tags, and `expected_verdict` /
  `expected_outcome` where applicable.
- Datasets are version-controlled. Changes require review.
- Minimum dataset sizes are **hard requirements**, not suggestions.

### Dataset Summary

| File | Min Count | Purpose |
|------|-----------|---------|
| `generation.json` | 50 | Game generation (15 simple / 20 medium / 15 hard) |
| `adversarial.json` | 70 | 50+ attacks + 20 legitimate |
| `edge_cases.json` | 15 | Malformed / ambiguous / multilingual / empty / long |
| `output_violations.json` | 40 | 20+ violations + 20 clean |
| `preference_scenarios.json` | 15 | Cross-session preference flows |
| `reliability_faults.json` | 10 | Fault injection scenarios |

---

## 5. Report Specification

### Rule: every eval run MUST produce both

1. **JSON report** → `eval/reports/{date}_{dimension}.json` (gitignored)
2. **Markdown report** → `docs/evals/{dimension}-report.md` (committed)

### Markdown Report Template (mandatory sections)

Every `docs/evals/*.md` report MUST contain these sections in order:

```markdown
# {Dimension Name} Eval Report

## 1. Summary

One-paragraph executive summary: what was tested, key result, pass/fail
against targets.

## 2. Methodology

- Dataset: file, count, composition
- Runner: script path, command to reproduce
- Environment: model, config, sandbox backend, git SHA
- Date of run

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| ...    | ...   | ...    | ✅ / ❌ |

### 3.2 Breakdown

Per-complexity / per-category / per-model breakdown tables as applicable.

### 3.3 Distribution

Histograms or percentile tables for latency / rounds / token usage.

## 4. Failure Analysis

For each failed case:
- ID, prompt (truncated), failure category, error detail, wall-clock time.
- Root cause analysis where identifiable.

## 5. Improvement History

| Date | Git SHA | Change | Key Metric | Before | After | Delta |
|------|---------|--------|-----------|--------|-------|-------|
| ...  | ...     | Baseline | ...     | ...    | ...   | -     |
| ...  | ...     | Fix X    | ...     | ...    | ...   | +N%   |

## 6. Below-Target Items

List of metrics that are below production target.
For each: root cause hypothesis, proposed fix, estimated effort.
**These items MUST be aligned with the user before implementation.**

## 7. Conclusion

Overall assessment. Next steps.
```

### Dashboard (`docs/evals/dashboard.md`)

`run_all.py` generates a cross-dimension dashboard after a full suite run:

```markdown
# GameForge Eval Dashboard

> Last full run: {date} | Git SHA: {sha} | Model: {model}

| Dimension | Key Metric | Value | Target | Status |
|-----------|-----------|-------|--------|--------|
| Generation Success | success_rate | 90.0% | ≥ 90% | ✅ |
| Code Quality | repair_effectiveness | 72.0% | ≥ 70% | ✅ |
| Security Guardrail | block_rate | 96.0% | ≥ 95% | ✅ |
| Security Encoding | encoding_bypass_block_rate | 60.0% | ≥ 90% | ❌ |
| Performance | sandbox_exec_p95 | 12.3s | ≤ 30s | ✅ |
| Output Audit | violation_detection_rate | 91.0% | ≥ 90% | ✅ |
| Model Comparison | best_model | DeepSeek-V4 | - | - |
| Preference | cross_session_injection | 100% | 100% | ✅ |
| Reliability | checkpoint_resume | 100% | 100% | ✅ |

## Below-Target Items (requires action)

| Dimension | Metric | Current | Target | Gap |
|-----------|--------|---------|--------|-----|
| Security | encoding_bypass_block_rate | 60.0% | ≥ 90% | -30% |

> ⚠️ Items above MUST be fixed. Optimisation plan must be aligned before
> implementation begins.
```

### JSON Report Schema (per_run detail)

```json
{
  "id": "gen-001",
  "prompt": "...",
  "complexity": "simple",
  "status": "done",
  "success": true,
  "wall_clock_s": 95.2,
  "token_usage": {
    "plan": 2100,
    "code_gen": 12000,
    "diagnose": 0,
    "repair": 0,
    "total": 14100
  },
  "phases": {
    "plan_s": 8.5,
    "code_gen_s": 45.2,
    "playtest_s": 12.1,
    "total_s": 95.2
  },
  "qa_rounds": 1,
  "qa_first_attempt_pass": true,
  "failure_category": null,
  "error_detail": null
}
```

---

## 6. Below-Target Workflow

When any metric falls below its production target:

```text
1. Runner flags metric as ❌ in report
2. Report Section 6 lists root cause hypothesis + proposed fix
3. *** STOP — align proposed fix with user before proceeding ***
4. User approves → create fix branch
5. Implement fix
6. Re-run eval → produce delta report
7. Update Improvement History table (Section 5) with before/after data
8. If still below target → repeat from step 2
9. If all targets met → commit report + code, create PR
```

**Hard rule**: no fix implementation starts without user alignment on the
approach. This prevents wasted effort on suboptimal solutions.

---

## 7. Implementation Plan

### Phase 1: Foundation

| Issue | Scope | Deliverable |
|-------|-------|-------------|
| [#115](https://github.com/ByteTitan-star/GameForge-Copilot/issues/115) | Eval infra + generation eval | `eval/` scaffold, dataset, runner, `docs/evals/generation-eval-report.md` |
| [#119](https://github.com/ByteTitan-star/GameForge-Copilot/issues/119) | Security eval + adversarial dataset | Dataset, runner, `docs/evals/security-eval-report.md` |
| [#120](https://github.com/ByteTitan-star/GameForge-Copilot/issues/120) | Encoding bypass fix | Guard decode preprocessing, delta in security report |

### Phase 2: Quality & Performance

| Issue | Scope | Deliverable |
|-------|-------|-------------|
| [#116](https://github.com/ByteTitan-star/GameForge-Copilot/issues/116) | Code quality eval | Runner, `docs/evals/code-quality-eval-report.md` |
| [#117](https://github.com/ByteTitan-star/GameForge-Copilot/issues/117) | Performance benchmark | Runner, `docs/evals/performance-eval-report.md` |

### Phase 3: Audit & Hardening

| Issue | Scope | Deliverable |
|-------|-------|-------------|
| [#121](https://github.com/ByteTitan-star/GameForge-Copilot/issues/121) | Output audit eval | Dataset, runner, `docs/evals/output-audit-eval-report.md` |
| [#122](https://github.com/ByteTitan-star/GameForge-Copilot/issues/122) | Guard hit → AuditLog | Persistence code, verified in audit eval |

### Phase 4: Advanced Dimensions (new issues needed)

| Scope | Deliverable |
|-------|-------------|
| Model comparison eval | Runner, dataset subset, `docs/evals/model-comparison-report.md` |
| Preference persistence eval | Dataset, runner, `docs/evals/preference-eval-report.md` |
| Reliability fault injection eval | Dataset, runner, `docs/evals/reliability-eval-report.md` |

### Phase 5: CI Integration

| Issue | Scope | Deliverable |
|-------|-------|-------------|
| [#118](https://github.com/ByteTitan-star/GameForge-Copilot/issues/118) | CI eval gate | GitHub Actions workflow, regression blocking |

### Full Suite Dashboard

After all phases complete, `run_all.py` produces `docs/evals/dashboard.md`.

### Workflow per Issue

```text
1. Create branch from main
2. Implement eval runner + dataset
3. Run eval → produce baseline JSON report + markdown report
4. If metric below target:
   a. Document root cause in report Section 6
   b. *** Align fix approach with user ***
   c. Implement fix
   d. Re-run eval → update report with delta
5. Commit: report (docs/evals/*.md) + code + dataset
6. PR with report data as evidence
```
