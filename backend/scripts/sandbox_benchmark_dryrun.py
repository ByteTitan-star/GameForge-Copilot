"""CLI：uv run python -m scripts.sandbox_benchmark_dryrun --rounds 5"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 允许 `python scripts/...` 与 `python -m` 两种调用
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.sandbox.benchmark import run_benchmark  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sandbox benchmark dry-run (local default)")
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args(argv)
    report = asyncio.run(run_benchmark(rounds=max(1, args.rounds)))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
