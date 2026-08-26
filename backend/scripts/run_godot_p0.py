"""Local PoC: materialize Godot template and run P0 loop.

Usage:
  cd backend && uv run python -m scripts.run_godot_p0 --workspace /tmp/gf-godot
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.forge.native.godot.diagnostics import structured_from_loop_result
from app.forge.native.godot.pipeline import run_godot_p0_loop
from app.forge.native.godot.template_loader import materialize_godot_template


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Godot P0 validate/build/run loop.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("artifacts/godot-p0"),
        help="Workspace directory (template copied if empty)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Re-copy template even if project.godot exists",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    ws: Path = args.workspace
    if args.fresh or not (ws / "project.godot").is_file():
        materialize_godot_template(ws)
    result = await run_godot_p0_loop(ws)
    structured = structured_from_loop_result(result)
    print(json.dumps(structured.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
