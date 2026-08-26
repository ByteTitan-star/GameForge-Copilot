"""Knowledge RAG 离线检索评测（ADR-14 §4）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    node: str
    input: str
    design_doc: dict[str, Any] | None
    expect_domains: tuple[str, ...]


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    hit_count: int
    domains: tuple[str, ...]
    ok: bool
    titles: tuple[str, ...]


@dataclass(frozen=True)
class EvalReport:
    total: int
    passed: int
    results: tuple[EvalCaseResult, ...]


def load_eval_cases(path: Path) -> list[EvalCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise ValueError('eval file must contain {"cases": [...]}')
    cases: list[EvalCase] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"cases[{idx}] must be object")
        cases.append(
            EvalCase(
                id=str(item.get("id") or f"case-{idx}"),
                node=str(item.get("node") or "plan"),
                input=str(item.get("input") or ""),
                design_doc=item.get("design_doc")
                if isinstance(item.get("design_doc"), dict)
                else None,
                expect_domains=tuple(item.get("expect_domains") or ()),
            )
        )
    return cases


async def run_eval_cases(cases: list[EvalCase]) -> EvalReport:
    from app.forge.knowledge.retriever import retrieve_knowledge_for_node

    results: list[EvalCaseResult] = []
    passed = 0
    for case in cases:
        hits = await retrieve_knowledge_for_node(
            node=case.node,
            current_input=case.input,
            design_doc=case.design_doc,
        )
        domains = tuple(sorted({h.domain for h in hits if h.domain}))
        ok = len(hits) > 0
        if case.expect_domains:
            ok = ok and any(d in domains for d in case.expect_domains)
        if ok:
            passed += 1
        results.append(
            EvalCaseResult(
                case_id=case.id,
                hit_count=len(hits),
                domains=domains,
                ok=ok,
                titles=tuple(h.title for h in hits),
            )
        )
    return EvalReport(total=len(cases), passed=passed, results=tuple(results))
