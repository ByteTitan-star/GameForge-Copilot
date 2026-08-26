"""Knowledge RAG 一键运维：probe → ingest → eval（#143）。

Usage:
  cd backend && uv run python -m scripts.knowledge_bootstrap
  cd backend && uv run python -m scripts.knowledge_bootstrap --skip-probe --ingest-only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.core.config import settings
from app.forge.knowledge.eval import load_eval_cases, run_eval_cases
from app.forge.knowledge.ingest import ingest_corpus_file, load_corpus_file
from app.forge.knowledge.probe import probe_knowledge_stack
from app.forge.knowledge.verify import verify_knowledge_retrieval

_DEFAULT_CORPUS = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "forge"
    / "knowledge"
    / "corpus"
    / "sample_seed.json"
)
_DEFAULT_EVAL = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "forge"
    / "knowledge"
    / "corpus"
    / "eval_queries.json"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap gameforge-knowledge index.")
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument("--eval-file", type=Path, default=_DEFAULT_EVAL)
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--write-probe", action="store_true", help="Probe with upsert round-trip")
    parser.add_argument("--dry-run", action="store_true", help="Ingest dry-run only")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    if not args.skip_probe:
        probe = await probe_knowledge_stack(write_probe=args.write_probe)
        print(
            f"probe: ok={probe.ok} dim={probe.vector_dim} matches={probe.query_matches} "
            f"write={probe.write_probe_ok}"
        )
        if probe.hints:
            for hint in probe.hints:
                print(f"  hint: {hint}")
        if not probe.ok:
            return 1

    if not args.skip_ingest:
        if not args.corpus.is_file():
            print(f"corpus not found: {args.corpus}", file=sys.stderr)
            return 1
        result = await ingest_corpus_file(args.corpus, dry_run=args.dry_run)
        print(f"ingest: upserted={result.upserted} skipped={result.skipped} total={result.total}")
        if result.errors:
            for err in result.errors:
                print(f"  error: {err}", file=sys.stderr)
            if result.upserted == 0:
                return 2
        if not args.dry_run and result.upserted > 0:
            chunks = load_corpus_file(args.corpus)
            ok, detail = await verify_knowledge_retrieval(chunks)
            print(f"verify: ok={ok} {detail}")
            if not ok:
                return 3

    if not args.skip_eval:
        if not settings.knowledge_rag_enabled:
            settings.knowledge_rag_enabled = True
        if not args.eval_file.is_file():
            print(f"eval file not found: {args.eval_file}", file=sys.stderr)
            return 1
        cases = load_eval_cases(args.eval_file)
        report = await run_eval_cases(cases)
        print(f"eval: passed={report.passed}/{report.total}")
        for row in report.results:
            status = "PASS" if row.ok else "FAIL"
            print(f"  [{status}] {row.case_id} hits={row.hit_count} domains={list(row.domains)}")
        if report.passed != report.total:
            return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
