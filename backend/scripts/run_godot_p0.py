"""Local PoC: materialize Godot template and run P0 loop.

Usage (host Godot CLI):
  cd backend && uv run python -m scripts.run_godot_p0 --workspace /tmp/gf-godot

Usage (Docker; requires gameforge-godot-builder image):
  docker compose --profile build-godot build godot-builder
  cd backend && uv run python -m scripts.run_godot_p0 --docker --workspace /tmp/gf-godot
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import settings
from app.forge.native.godot.adapter import GodotAdapter
from app.forge.native.godot.diagnostics import structured_from_loop_result
from app.forge.native.godot.pipeline import run_godot_p0_loop
from app.forge.native.godot.runner import GodotRunner
from app.forge.native.godot.template_loader import godot_template_root, materialize_godot_template

DEFAULT_DOCKER_IMAGE = "gameforge-godot-builder:v1"


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
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Run Godot via docker run (needs gameforge-godot-builder image)",
    )
    parser.add_argument(
        "--docker-image",
        default="",
        help=f"Docker image (default: env or {DEFAULT_DOCKER_IMAGE})",
    )
    return parser.parse_args()


def _resolve_docker_image(cli_value: str) -> str:
    if cli_value.strip():
        return cli_value.strip()
    if settings.native_engine_godot_docker_image.strip():
        return settings.native_engine_godot_docker_image.strip()
    return DEFAULT_DOCKER_IMAGE


def _build_adapter(*, use_docker: bool, docker_image: str) -> GodotAdapter | None:
    if not use_docker:
        return None
    runner = GodotRunner(
        godot_bin="",
        docker_image=docker_image,
        build_timeout_s=float(settings.native_engine_godot_build_timeout_s),
        run_timeout_s=float(settings.native_engine_godot_run_timeout_s),
    )
    return GodotAdapter(
        godot_version=settings.native_engine_godot_version,
        template_root=godot_template_root(),
        runner=runner,
    )


async def main() -> int:
    args = _parse_args()
    ws: Path = args.workspace
    if args.fresh or not (ws / "project.godot").is_file():
        materialize_godot_template(ws)
    adapter = _build_adapter(
        use_docker=args.docker,
        docker_image=_resolve_docker_image(args.docker_image),
    )
    result = await run_godot_p0_loop(ws, adapter=adapter)
    structured = structured_from_loop_result(result)
    print(json.dumps(structured.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
