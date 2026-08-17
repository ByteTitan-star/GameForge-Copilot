# ADR Accept Checklist

> Owner sign-off: **ByteTitan-star** (2026-08-16).
> Design-review follow-up: [ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md).

## 签字区

| ADR | Reviewer | Date | Decision |
| --- | --- | --- | --- |
| ADR-02 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-03 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-03 revision 2026-08-16 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-04 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-05 revision 2026-08-16 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-06 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-07 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-08 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-09 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-10 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-11 | ByteTitan-star | 2026-08-16 | Accept |
| ADR-12 (Sections A/B/C) | ByteTitan-star | 2026-08-16 | Accept |

## Machine evidence

```bash
cd backend && uv run pytest tests/test_adr_evidence.py -q
```

`app/forge/adr_evidence.py` checks runtime invariants aligned with Accepted decisions
(Daytona preferred, inferred+cap=50, forge_messages SoT, semantic direct-hit still forbidden).
ADR-07～12 evidence hooks may be added as implementation lands.
