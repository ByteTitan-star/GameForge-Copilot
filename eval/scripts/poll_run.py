"""Resume polling an in-flight eval run (dev helper)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_REPO), str(_REPO / "backend")]

from eval.runners.generation_eval import _poll_run  # noqa: E402
import httpx  # noqa: E402


async def main() -> None:
    token = os.environ.get("EVAL_ACCESS_TOKEN", "")
    game_id = os.environ["EVAL_GAME_ID"]
    run_id = os.environ["EVAL_RUN_ID"]
    base = os.environ.get("EVAL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    async with httpx.AsyncClient(
        base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=120.0
    ) as client:
        result = await _poll_run(
            client,
            game_id=game_id,
            run_id=run_id,
            timeout_s=float(os.environ.get("EVAL_RUN_TIMEOUT_S", "900")),
            poll_interval_s=float(os.environ.get("EVAL_POLL_INTERVAL_S", "5")),
            max_hitl=int(os.environ.get("EVAL_MAX_HITL", "8")),
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
