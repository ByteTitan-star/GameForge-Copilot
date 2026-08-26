"""Curated knowledge corpus 入库 CLI（ADR-14 §3.5）。

用法：
  cd backend && uv run python -m scripts.ingest_knowledge
  cd backend && uv run python -m scripts.ingest_knowledge --file path/to/corpus.json
  cd backend && uv run python -m scripts.ingest_knowledge --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.forge.knowledge.ingest import ingest_corpus_file

_DEFAULT_CORPUS = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "forge"
    / "knowledge"
    / "corpus"
    / "sample_seed.json"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest curated knowledge chunks into Pinecone.")
    parser.add_argument(
        "--file",
        type=Path,
        default=_DEFAULT_CORPUS,
        help="JSON corpus file (default: bundled sample_seed.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate only; do not upsert",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    path: Path = args.file
    if not path.is_file():
        print(f"corpus file not found: {path}", file=sys.stderr)
        return 1
    result = await ingest_corpus_file(path, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "ingest"
    print(
        f"ingest_knowledge ({mode}): total={result.total} "
        f"upserted={result.upserted} skipped={result.skipped}"
    )
    if result.errors:
        print("errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 2 if result.upserted == 0 else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
