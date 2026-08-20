"""Dimension 6: Cross-model comparison benchmark.

Issue: #123

Offline mode validates comparison subset + model registry.
Live mode runs generation subset per model (requires EVAL_LIVE + credentials).
"""

from __future__ import annotations

import json
import os
import sys
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
    load_dataset,
    report_header,
    write_json_report,
    write_markdown,
)


def run_eval() -> dict[str, Any]:
    cfg = json.loads((Path(__file__).resolve().parent.parent / "datasets" / "model_comparison.json").read_text(encoding="utf-8"))
    generation = load_dataset("generation.json")
    by_id = {c["id"]: c for c in generation}
    subset = [by_id[i] for i in cfg["subset_ids"] if i in by_id]
    live = os.environ.get("EVAL_LIVE", "").lower() in {"1", "true", "yes"}

    per_model = []
    for model in cfg["models"]:
        per_model.append(
            {
                "model_id": model["id"],
                "provider": model["provider"],
                "prompts_planned": len(subset),
                "runs_completed": 0 if not live else 0,
                "success_rate": None,
                "note": "live run pending — configure per-model API keys",
            }
        )

    summary = {
        "subset_size": len(subset),
        "models": len(cfg["models"]),
        "mode": "live" if live else "offline_registry",
    }

    report = base_report_meta(
        dimension="model_comparison",
        runner="eval/runners/model_comparison_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["subset"] = [{"id": c["id"], "complexity": c["complexity"]} for c in subset]
    report["per_model"] = per_model
    report["instructions"] = (
        "Live comparison: set EVAL_LIVE=1 and run generation_eval --live per model config."
    )
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="Cross-Model Comparison Report",
        summary=(
            f"Comparison registry with **{s['models']}** models and "
            f"**{s['subset_size']}** fixed generation prompts."
        ),
        runner="eval/runners/model_comparison_eval.py",
        dataset="eval/datasets/model_comparison.json",
        dataset_count=s["subset_size"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    lines += [
        "| Model | Provider | Prompts | Success Rate |",
        "|-------|----------|---------|--------------|",
    ]
    for m in report["per_model"]:
        rate = m["success_rate"] if m["success_rate"] is not None else "n/a"
        lines.append(
            f"| {m['model_id']} | {m['provider']} | {m['prompts_planned']} | {rate} |"
        )
    lines += ["", "## 7. Conclusion", "", report["instructions"], ""]
    return write_markdown(DOCS_EVALS_DIR / "model-comparison-report.md", lines)


def main() -> None:
    report = run_eval()
    json_path = write_json_report("model_comparison_eval", report)
    md_path = write_markdown_report(report)
    print(f"mode={report['summary']['mode']}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
