# Security Guardrail Eval Report

## 1. Summary

Tested **89** cases (59 adversarial + 30 legitimate) against regex blacklist and AC lexicon layers (no LLM audit). Overall block rate: **100.0%**, false-positive rate: **0.0%**, encoding bypass block rate: **100.0%**.

## 2. Methodology

- **Dataset**: `eval/datasets/adversarial.json` + `eval/datasets/edge_cases.json` (89 entries, 15 edge cases)
- **Runner**: `eval/runners/security_eval.py`
- **Reproduce**: `cd backend && uv run python -m eval.runners.security_eval`
- **Layers tested**: regex blacklist + Aho-Corasick lexicon (no LLM audit)
- **Git SHA**: `fb547ea`
- **Date**: 2026-08-25

## 3. Results

### 3.1 Metrics Table

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| block_rate | 100.0% | >= 95% | ✅ |
| false_positive_rate | 0.0% | <= 2% | ✅ |
| encoding_bypass_block_rate | 100.0% | >= 90% | ✅ |
| edge_case_pass_rate | 100.0% | >= 90% | ✅ |
| avg_latency_ms | 0.50ms | - | - |

### 3.2 Breakdown by Attack Type

| Attack Type | Total | Correct | Rate |
|-------------|-------|---------|------|
| edge_case | 15 | 15 | 100.0% |
| encoding_bypass | 19 | 19 | 100.0% |
| gambling_drugs | 5 | 5 | 100.0% |
| malicious_code | 5 | 5 | 100.0% |
| none | 20 | 20 | 100.0% |
| politics | 5 | 5 | 100.0% |
| porn | 5 | 5 | 100.0% |
| prompt_injection | 10 | 10 | 100.0% |
| terrorism | 5 | 5 | 100.0% |

### 3.3 Breakdown by Encoding

| Encoding | Total | Correct | Rate |
|----------|-------|---------|------|
| base64 | 4 | 4 | 100.0% |
| base64_mixed | 2 | 2 | 100.0% |
| html_entity | 5 | 5 | 100.0% |
| mixed | 1 | 1 | 100.0% |
| plain | 70 | 70 | 100.0% |
| rot13 | 2 | 2 | 100.0% |
| unicode_escape | 5 | 5 | 100.0% |

### 3.4 Catching Layer Distribution

| Layer | Hits |
|-------|------|
| lexicon | 28 |
| regex | 31 |

## 4. Failure Analysis

No failures detected.

## 5. Improvement History

| Date | Git SHA | Change | block_rate | encoding_bypass | Delta |
|------|---------|--------|-----------|-----------------|-------|
| 2026-08-25 | fb547ea | Baseline (regex+lexicon only) | 100.0% | 100.0% | - |

## 6. Below-Target Items

All metrics meet production targets. No action required.

## 7. Conclusion

All security guardrail metrics meet production targets.
