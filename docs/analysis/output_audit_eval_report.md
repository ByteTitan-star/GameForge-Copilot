# Output Audit Coverage Eval Report (Quick Filter Baseline)

## 1. Summary

This eval measures output-side content moderation effectiveness using Guard `quick_filter()` only (regex blacklist + AC lexicon, no LLM).

- Detection rate: **95.0%** (target >= 90%) ✅
- False-positive rate: **0.0%** (target < 3%) ✅
- Audit latency p95: **1.496 ms**

## 2. Methodology

- Dataset: `eval/datasets/output_violations.json`
- Runner: `eval/runners/output_audit_eval.py`
- Layers tested: regex blacklist + AC lexicon (no LLM)
- Timestamp: 2026-08-21T15:41:06.650921+00:00

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|---|---:|---|---|
| detection_rate | 95.0% | >= 90% | ✅ |
| false_positive_rate | 0.0% | < 3% | ✅ |
| audit_latency_p95_ms | 1.496ms | documented | ✅ |

### 3.2 Breakdown by Violation Type

| Violation Type | Total | Flagged | Rate |
|---|---:|---:|---:|
| javascript_scheme | 2 | 2 | 100.0% |
| mixed | 3 | 3 | 100.0% |
| onerror_attr | 1 | 1 | 100.0% |
| onerror_fetch | 2 | 2 | 100.0% |
| onerror_sendBeacon | 1 | 1 | 100.0% |
| script_eval | 5 | 5 | 100.0% |
| sendBeacon | 3 | 2 | 66.7% |
| websocket | 3 | 3 | 100.0% |

## 4. Failure Analysis

### False Positives

- None

## 5. Conclusion

Quick-filter baseline results: detection_rate=95.0%, false_positive_rate=0.0%, audit_latency_p95_ms=1.496ms.
