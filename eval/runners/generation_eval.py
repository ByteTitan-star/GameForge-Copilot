"""Dimension 1: Generation success rate eval.

Issue: #115

Modes:
  - offline (default): validate dataset + emit readiness report
  - live: requires EVAL_LIVE=1, EVAL_API_BASE_URL, EVAL_ACCESS_TOKEN
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from eval.runners._common import (
    DOCS_EVALS_DIR,
    base_report_meta,
    below_target_section,
    load_dataset,
    report_header,
    status_cell,
    write_json_report,
    write_markdown,
)


def _validate_dataset(dataset: list[dict[str, Any]]) -> dict[str, Any]:
    by_complexity = Counter(c.get("complexity", "unknown") for c in dataset)
    return {
        "total": len(dataset),
        "simple": by_complexity.get("simple", 0),
        "medium": by_complexity.get("medium", 0),
        "hard": by_complexity.get("hard", 0),
        "valid": len(dataset) >= 50,
    }


async def _run_live(dataset: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    import httpx

    base = os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")
    token = os.environ.get("EVAL_ACCESS_TOKEN", "")
    if not base or not token:
        raise RuntimeError("EVAL_API_BASE_URL and EVAL_ACCESS_TOKEN required for live mode")

    headers = {"Authorization": f"Bearer {token}"}
    per_run: list[dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=60.0) as client:
        for case in dataset[:limit]:
            # Minimal live hook: create game draft then run (API shape may evolve)
            resp = await client.post(
                "/api/v1/games",
                json={"title": case["id"], "prompt": case["prompt"]},
            )
            ok = resp.status_code in {200, 201}
            per_run.append(
                {
                    "id": case["id"],
                    "complexity": case["complexity"],
                    "success": ok,
                    "status_code": resp.status_code,
                    "failure_category": None if ok else "api_error",
                }
            )
    return per_run


def run_eval(*, live: bool, limit: int) -> dict[str, Any]:
    dataset = load_dataset("generation.json")
    validation = _validate_dataset(dataset)
    mode = "live" if live else "offline"

    report = base_report_meta(
        dimension="generation_success",
        runner="eval/runners/generation_eval.py",
        mode=mode,
    )
    report["dataset_validation"] = validation

    if live:
        per_run = asyncio.run(_run_live(dataset, limit=limit))
        successes = sum(1 for r in per_run if r["success"])
        n = max(1, len(per_run))
        summary = {
            "prompts_run": len(per_run),
            "success_rate": round(successes / n, 4),
            "mode": "live_partial",
        }
        report["per_run"] = per_run
    else:
        summary = {
            "prompts_run": 0,
            "success_rate": None,
            "dataset_ready": validation["valid"],
            "mode": "offline_readiness",
        }
        report["per_run"] = []
        report["instructions"] = (
            "Set EVAL_LIVE=1, EVAL_API_BASE_URL, EVAL_ACCESS_TOKEN then rerun with --live."
        )

    report["summary"] = summary
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    from pathlib import Path

    s = report["summary"]
    v = report["dataset_validation"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    mode = s["mode"]

    if mode == "offline_readiness":
        summary_text = (
            f"Dataset validation: **{v['total']}** prompts "
            f"({v['simple']} simple / {v['medium']} medium / {v['hard']} hard). "
            "Live generation not executed."
        )
    else:
        summary_text = (
            f"Live partial run on **{s['prompts_run']}** prompts. "
            f"Success rate: **{s['success_rate']:.1%}**."
        )

    lines = report_header(
        title="Generation Success Rate Eval Report",
        summary=summary_text,
        runner="eval/runners/generation_eval.py",
        dataset="eval/datasets/generation.json",
        dataset_count=v["total"],
        mode=mode,
        sha=sha,
        ts=ts,
    )

    if s.get("success_rate") is not None:
        lines += [
            f"| success_rate | {s['success_rate']:.1%} | >= 90% | "
            f"{status_cell(s['success_rate'], 0.90, higher_is_better=True)} |",
        ]
    else:
        lines += [
            f"| dataset_ready (>=50 prompts) | {v['valid']} | true | "
            f"{'✅' if v['valid'] else '❌'} |",
            "| success_rate | n/a (offline) | >= 90% | ⏳ |",
        ]

    lines += ["", "## 7. Conclusion", ""]
    if mode == "offline_readiness":
        lines.append(report.get("instructions", "Run with --live when API is configured."))
    else:
        lines.append("Partial live run complete. Scale to full 50+ prompts for production gate.")
    lines.append("")

    below = []
    if s.get("success_rate") is not None and s["success_rate"] < 0.90:
        below.append(f"- success_rate {s['success_rate']:.1%} below 90% target")
    if not v["valid"]:
        below.append("- generation.json has fewer than 50 prompts")
    lines.extend(below_target_section(below))
    return write_markdown(DOCS_EVALS_DIR / "generation-eval-report.md", lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generation success rate eval")
    parser.add_argument("--live", action="store_true", help="Run live API subset")
    parser.add_argument("--limit", type=int, default=3, help="Live prompt limit")
    args = parser.parse_args()
    live = args.live or os.environ.get("EVAL_LIVE", "").lower() in {"1", "true", "yes"}
    report = run_eval(live=live, limit=args.limit)
    json_path = write_json_report("generation_eval", report)
    md_path = write_markdown_report(report)
    print(f"mode={report['summary']['mode']}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
