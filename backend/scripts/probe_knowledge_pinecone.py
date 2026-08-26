"""Knowledge RAG Pinecone + Embedding connectivity probe CLI (#143).

Usage:
  cd backend && uv run python -m scripts.probe_knowledge_pinecone
  cd backend && uv run python -m scripts.probe_knowledge_pinecone --write-probe

Prerequisites (.env):
  EMBEDDING_* + PINECONE_API_KEY + PINECONE_KNOWLEDGE_HOST
  (do NOT point knowledge host at gameforge-semantic / PINECONE_HOST)
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.forge.knowledge.probe import probe_knowledge_stack


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Embedding + Pinecone gameforge-knowledge connectivity.",
    )
    parser.add_argument(
        "--write-probe",
        action="store_true",
        help="Upsert and read back a probe vector (validates write path)",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    result = await probe_knowledge_stack(write_probe=args.write_probe)
    print(
        "probe_knowledge: "
        f"ok={result.ok} embedding={result.embedding_ok} pinecone={result.pinecone_ok} "
        f"dim={result.vector_dim} query_matches={result.query_matches} "
        f"write_probe={result.write_probe_ok}"
    )
    if result.hints:
        print("hints:")
        for hint in result.hints:
            print(f"  - {hint}")
    if result.errors:
        print("errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
