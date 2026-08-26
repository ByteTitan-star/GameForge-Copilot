"""Curated knowledge corpus 入库 CLI（ADR-14 §3.5）。

用法：
  cd backend && uv run python -m scripts.ingest_knowledge
  cd backend && uv run python -m scripts.ingest_knowledge --file path/to/corpus.json
  cd backend && uv run python -m scripts.ingest_knowledge --dry-run
  cd backend && uv run python -m scripts.ingest_knowledge --verify

运维顺序（真实 Pinecone）：
  1. 创建 Index gameforge-knowledge（dim=512，与 bge-small-zh-v1.5 一致）
  2. 配置 .env：EMBEDDING_* + PINECONE_API_KEY + PINECONE_KNOWLEDGE_HOST
  3. uv run python -m scripts.probe_knowledge_pinecone --write-probe
  4. uv run python -m scripts.ingest_knowledge --verify
  5. uv run python -m scripts.eval_knowledge_rag
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.forge.knowledge.ingest import ingest_corpus_file, load_corpus_file
from app.forge.knowledge.verify import verify_knowledge_retrieval

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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After ingest, run a retrieval smoke test on first chunk",
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

    if args.verify and not args.dry_run and result.upserted > 0:
        chunks = load_corpus_file(path)
        ok, detail = await verify_knowledge_retrieval(chunks)
        print(f"verify_retrieval: ok={ok} {detail}")
        if not ok:
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
