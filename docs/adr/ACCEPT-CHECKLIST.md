# ADR Accept Checklist

> Owner sign-off: **ByteTitan-star** (2026-08-16). Status on ADR-02/03/04 set to **Accepted**.

## 签字区

| ADR | Reviewer | Date | Decision |
| --- | --- | --- | --- |
| ADR-02 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-03 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-04 | ByteTitan-star | 2026-08-16 | Accept |

## Machine evidence

```bash
cd backend && uv run pytest tests/test_adr_evidence.py -q
```

`app/forge/adr_evidence.py` checks runtime invariants aligned with Accepted decisions
(E2B preferred, inferred+cap=50, forge_messages SoT, semantic direct-hit still forbidden).
