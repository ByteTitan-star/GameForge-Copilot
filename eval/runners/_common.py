"""Shared helpers for eval runners."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVAL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = EVAL_ROOT.parent
BACKEND_DIR = REPO_ROOT / "backend"
DATASETS_DIR = EVAL_ROOT / "datasets"
REPORTS_DIR = EVAL_ROOT / "reports"
DOCS_EVALS_DIR = REPO_ROOT / "docs" / "evals"

REPORTS_DIR.mkdir(exist_ok=True)
DOCS_EVALS_DIR.mkdir(parents=True, exist_ok=True)


def setup_backend_path() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=REPO_ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def load_dataset(name: str) -> list[dict[str, Any]]:
    path = DATASETS_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if p <= 0:
        return sorted_values[0]
    if p >= 1:
        return sorted_values[-1]
    idx = int(p * (len(sorted_values) - 1))
    return sorted_values[idx]


def status_cell(value: float, target: float, *, higher_is_better: bool) -> str:
    ok = value >= target if higher_is_better else value <= target
    return "✅" if ok else "❌"


def write_json_report(dimension: str, report: dict[str, Any]) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"{date_str}_{dimension}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_markdown(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def base_report_meta(*, dimension: str, runner: str, mode: str) -> dict[str, Any]:
    return {
        "eval_dimension": dimension,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "runner": runner,
        "mode": mode,
        "environment": {
            "eval_api_base_url": os.environ.get("EVAL_API_BASE_URL", ""),
            "eval_live_enabled": os.environ.get("EVAL_LIVE", "").lower() in {"1", "true", "yes"},
        },
    }


def report_header(
    *,
    title: str,
    summary: str,
    runner: str,
    dataset: str,
    dataset_count: int,
    mode: str,
    sha: str,
    ts: str,
) -> list[str]:
    return [
        f"# {title}",
        "",
        "## 1. Summary",
        "",
        summary,
        "",
        "## 2. Methodology",
        "",
        f"- **Dataset**: `{dataset}` ({dataset_count} entries)",
        f"- **Runner**: `{runner}`",
        f"- **Mode**: `{mode}`",
        f"- **Reproduce**: `cd backend && uv run python -m eval.runners.<module>`",
        f"- **Git SHA**: `{sha}`",
        f"- **Date**: {ts[:10]}",
        "",
        "## 3. Results",
        "",
        "### 3.1 Metrics Table",
        "",
        "| Metric | Value | Target | Status |",
        "|--------|-------|--------|--------|",
    ]


def below_target_section(items: list[str]) -> list[str]:
    filtered = [item for item in items if item.strip()]
    lines = ["## 6. Below-Target Items", ""]
    if filtered:
        lines.append("> **Action required**: align fix approach with user before implementation.")
        lines.append("")
        lines.extend(filtered)
    else:
        lines.append("All metrics meet production targets for this mode.")
    lines.append("")
    return lines
