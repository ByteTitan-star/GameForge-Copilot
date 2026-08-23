"""Orchestrate all eval dimensions and refresh docs/evals/dashboard.md."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_EVAL_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_ROOT.parent
_REPORTS_DIR = _EVAL_ROOT / "reports"
_DOCS_EVALS = _REPO_ROOT / "docs" / "evals"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

RUNNERS: list[tuple[str, str, str, str]] = [
    ("#115", "generation_eval", "Generation Success", "generation_eval"),
    ("#116", "code_quality_eval", "Code Quality", "code_quality_eval"),
    ("#119", "security_eval", "Security Guardrail", "security_eval"),
    ("#117", "performance_eval", "Performance", "performance_eval"),
    ("#121", "output_audit_eval", "Output Audit", "output_audit_eval"),
    ("#123", "model_comparison_eval", "Model Comparison", "model_comparison_eval"),
    ("#124", "preference_eval", "Preference Persistence", "preference_eval"),
    ("#125", "reliability_eval", "Reliability", "reliability_eval"),
]


def _latest_report(prefix: str) -> dict | None:
    files = sorted(_REPORTS_DIR.glob(f"*_{prefix}.json"), reverse=True)
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))


def _row_from_report(name: str, report: dict | None) -> tuple[str, str, str, str]:
    if report is None:
        return name, "n/a", "-", "⏳"

    summary = report.get("summary") or {}
    dim = report.get("eval_dimension", "")

    if "generation" in dim or summary.get("mode") == "offline_readiness":
        val = summary.get("success_rate")
        if val is None:
            ready = summary.get("dataset_ready", report.get("dataset_validation", {}).get("valid"))
            return name, "offline", ">= 90%", "⏳" if ready else "❌"
        return name, f"{val:.1%}", ">= 90%", "✅" if val >= 0.90 else "❌"

    if summary.get("structure_detection_accuracy") is not None:
        val = summary["structure_detection_accuracy"]
        return name, f"{val:.1%}", ">= 90%", "✅" if val >= 0.90 else "❌"

    if summary.get("block_rate") is not None:
        val = summary["block_rate"]
        return name, f"{val:.1%}", ">= 95%", "✅" if val >= 0.95 else "❌"

    if summary.get("guard_p95_ms") is not None:
        return name, f"{summary['guard_p95_ms']:.3f}ms", "documented", "✅"

    if summary.get("detection_rate") is not None:
        val = summary["detection_rate"]
        return name, f"{val:.1%}", ">= 90%", "✅" if val >= 0.90 else "❌"

    if summary.get("cross_session_injection_rate") is not None:
        val = summary["cross_session_injection_rate"]
        return name, f"{val:.1%}", "100%", "✅" if val >= 1.0 else "❌"

    if summary.get("unit_pass_rate") is not None:
        val = summary["unit_pass_rate"]
        return name, f"{val:.1%}", ">= 90%", "✅" if val >= 0.90 else "❌"

    mode = summary.get("mode", "done")
    return name, str(mode), "-", "✅"


def write_dashboard(rows: list[tuple[str, str, str, str]]) -> Path:
    from eval.runners._common import git_sha, write_markdown

    ts = datetime.now(timezone.utc).isoformat()
    sha = git_sha()
    lines = [
        "# GameForge Eval Dashboard",
        "",
        f"> Last orchestrator run: {ts[:19]}Z | Git SHA: `{sha}`",
        "",
        "| Dimension | Value | Target | Status |",
        "|-----------|-------|--------|--------|",
    ]
    for name, value, target, status in rows:
        lines.append(f"| {name} | {value} | {target} | {status} |")
    lines += [
        "",
        "## Issue Coverage",
        "",
        "| Issue | Runner |",
        "|-------|--------|",
    ]
    for issue, module, _, _ in RUNNERS:
        lines.append(f"| {issue} | `eval/runners/{module}.py` |")
    lines += [
        "",
        "## Notes",
        "",
        "- #118 CI gate: `.github/workflows/eval.yml` (PR security+offline; main live generation `--limit 10`)",
        "- #122 AuditLog persistence: verified via `backend/scripts/verify_guard_auditlog_persistence.py`",
        "- Live generation: `EVAL_LIVE=1` + `EVAL_API_BASE_URL` + `EVAL_ACCESS_TOKEN`",
        "- Preference live API: `EVAL_PREF_LIVE=1` (separate from generation EVAL_LIVE)",
        "- Reliability fault sims: `EVAL_LIVE_FAULT=1` or workflow_dispatch `run_live_fault=true`",
        "",
    ]
    return write_markdown(_DOCS_EVALS / "dashboard.md", lines)


def main() -> None:
    rows: list[tuple[str, str, str, str]] = []

    for issue, module, name, json_prefix in RUNNERS:
        print(f"\n>>> {issue} {module}")
        try:
            mod = importlib.import_module(f"eval.runners.{module}")
            if hasattr(mod, "main"):
                mod.main()
            elif hasattr(mod, "run_eval"):
                report = mod.run_eval()
                if hasattr(mod, "write_markdown_report"):
                    mod.write_markdown_report(report)
                from eval.runners import _common as common

                common.write_json_report(json_prefix, report)
            report = _latest_report(json_prefix)
            rows.append(_row_from_report(name, report))
        except Exception as exc:
            print(f"ERROR: {exc}")
            rows.append((name, "error", "-", "❌"))

    path = write_dashboard(rows)
    print(f"\nDashboard: {path}")


if __name__ == "__main__":
    main()
