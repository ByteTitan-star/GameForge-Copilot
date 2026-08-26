"""Knowledge RAG offline retrieval eval CLI (#143).

Usage:
  cd backend && uv run python -m scripts.eval_knowledge_rag
  cd backend && uv run python -m scripts.eval_knowledge_rag --file <corpus.json>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.core.config import settings
from app.forge.knowledge.eval import load_eval_cases, run_eval_cases

_DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "forge"
    / "knowledge"
    / "corpus"
    / "eval_queries.json"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate knowledge RAG retrieval quality.")
    parser.add_argument("--file", type=Path, default=_DEFAULT, help="Eval cases JSON")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    if not args.file.is_file():
        print(f"eval file not found: {args.file}", file=sys.stderr)
        return 1
    if not settings.knowledge_rag_enabled:
        print("warning: KNOWLEDGE_RAG_ENABLED=false; enabling for eval run", file=sys.stderr)
        settings.knowledge_rag_enabled = True
    cases = load_eval_cases(args.file)
    report = await run_eval_cases(cases)
    print(f"knowledge_rag_eval: passed={report.passed}/{report.total}")
    for row in report.results:
        status = "PASS" if row.ok else "FAIL"
        titles = ", ".join(row.titles) if row.titles else "-"
        print(
            f"  [{status}] {row.case_id}: hits={row.hit_count} "
            f"domains={list(row.domains)} titles={titles}"
        )
    return 0 if report.passed == report.total else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
