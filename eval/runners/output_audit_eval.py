"""Dimension 5 (initial baseline): Output audit coverage eval.

This runner measures Guard's *output-side* content moderation effectiveness
using `quick_filter()` only (regex blacklist + AC lexicon). No LLM is used.

It produces:
  - `docs/evals/output-audit-eval-report.md` (committed)
  - `docs/analysis/output_audit_eval_report.md` (committed, mirrors report)
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.forge.guard import AuditResult, quick_filter  # noqa: E402


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    output: str
    expected: str  # "violation" | "clean"
    violation_type: str | None = None


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if p <= 0:
        return sorted_values[0]
    if p >= 1:
        return sorted_values[-1]
    idx = int(p * (len(sorted_values) - 1))
    return sorted_values[idx]


def _load_dataset(path: Path) -> list[Case]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Case(
            id=row["id"],
            output=row["output"],
            expected=row["expected"],
            violation_type=row.get("violation_type"),
        )
        for row in raw
    ]


def _flagged(res: AuditResult | None) -> bool:
    if res is None:
        return False
    return bool(res.is_malicious or res.suspected)


def run_eval() -> dict:
    dataset_path = _REPO_ROOT / "eval" / "datasets" / "output_violations.json"
    cases = _load_dataset(dataset_path)

    # Force quick_filter paths for deterministic baseline
    settings.audit_quick_filter = True
    settings.audit_lexicon_enabled = True

    tstamp = datetime.now(timezone.utc).isoformat()

    violations = [c for c in cases if c.expected == "violation"]
    clean = [c for c in cases if c.expected == "clean"]

    total_latencies_ms: list[float] = []
    by_type = {}
    per_case = []

    violation_flagged = 0
    clean_flagged = 0

    for c in cases:
        t0 = time.perf_counter()
        res = quick_filter(c.output, force=True)
        latency_ms = (time.perf_counter() - t0) * 1000
        total_latencies_ms.append(latency_ms)

        is_flag = _flagged(res)
        if c.expected == "violation":
            if is_flag:
                violation_flagged += 1
            if c.violation_type:
                by_type.setdefault(c.violation_type, {"total": 0, "flagged": 0})
                by_type[c.violation_type]["total"] += 1
                if is_flag:
                    by_type[c.violation_type]["flagged"] += 1
        else:
            if is_flag:
                clean_flagged += 1

        per_case.append(
            {
                "id": c.id,
                "expected": c.expected,
                "actual_flagged": is_flag,
                "latency_ms": round(latency_ms, 3),
                "guard_category": (res.category if res else None),
                "guard_reason": (res.reason if res else None),
                "suspected": (res.suspected if res else None),
            }
        )

    total_violations = max(1, len(violations))
    total_clean = max(1, len(clean))

    detection_rate = violation_flagged / total_violations
    false_positive_rate = clean_flagged / total_clean

    sorted_lat = sorted(total_latencies_ms)
    p95 = _percentile(sorted_lat, 0.95)

    result = {
        "eval_dimension": "output_audit_coverage_quick_filter_baseline",
        "timestamp": tstamp,
        "dataset_path": str(dataset_path.relative_to(_REPO_ROOT)),
        "summary": {
            "violations_total": len(violations),
            "clean_total": len(clean),
            "detection_rate": round(detection_rate, 4),
            "false_positive_rate": round(false_positive_rate, 4),
            "audit_latency_p95_ms": round(p95, 3),
            "avg_latency_ms": round(sum(total_latencies_ms) / len(total_latencies_ms), 3)
            if total_latencies_ms
            else 0.0,
            "latency_sample_size": len(total_latencies_ms),
        },
        "by_violation_type": {
            k: {"total": v["total"], "flagged": v["flagged"], "rate": round(v["flagged"] / max(1, v["total"]), 4)}
            for k, v in by_type.items()
        },
        "per_case": per_case,
    }
    return result


def _write_md(report: dict, out_path: Path) -> None:
    s = report["summary"]
    detection = s["detection_rate"]
    fp = s["false_positive_rate"]
    p95 = s["audit_latency_p95_ms"]

    detection_ok = detection >= 0.90
    fp_ok = fp < 0.03
    p95_ok = True  # no hard threshold defined beyond being documented

    lines = [
        "# Output Audit Coverage Eval Report (Quick Filter Baseline)",
        "",
        "## 1. Summary",
        "",
        "This eval measures output-side content moderation effectiveness using Guard `quick_filter()` only (regex blacklist + AC lexicon, no LLM).",
        "",
        f"- Detection rate: **{detection*100:.1f}%** (target >= 90%) {'✅' if detection_ok else '❌'}",
        f"- False-positive rate: **{fp*100:.1f}%** (target < 3%) {'✅' if fp_ok else '❌'}",
        f"- Audit latency p95: **{p95:.3f} ms**",
        "",
        "## 2. Methodology",
        "",
        "- Dataset: `eval/datasets/output_violations.json`",
        "- Runner: `eval/runners/output_audit_eval.py`",
        "- Layers tested: regex blacklist + AC lexicon (no LLM)",
        f"- Timestamp: {report['timestamp']}",
        "",
        "## 3. Results",
        "",
        "### 3.1 Metrics Table",
        "",
        "| Metric | Value | Target | Status |",
        "|---|---:|---|---|",
        f"| detection_rate | {detection*100:.1f}% | >= 90% | {'✅' if detection_ok else '❌'} |",
        f"| false_positive_rate | {fp*100:.1f}% | < 3% | {'✅' if fp_ok else '❌'} |",
        f"| audit_latency_p95_ms | {p95:.3f}ms | documented | {'✅' if p95_ok else '❌'} |",
        "",
        "### 3.2 Breakdown by Violation Type",
        "",
        "| Violation Type | Total | Flagged | Rate |",
        "|---|---:|---:|---:|",
    ]

    for vt, v in sorted(report["by_violation_type"].items(), key=lambda x: x[0]):
        rate = v["rate"]
        lines.append(f"| {vt} | {v['total']} | {v['flagged']} | {rate*100:.1f}% |")

    lines += [
        "",
        "## 4. Failure Analysis",
        "",
        "### False Positives",
        "",
    ]

    fps = [c for c in report["per_case"] if c["expected"] == "clean" and c["actual_flagged"]]
    if not fps:
        lines += ["- None"]
    else:
        lines.append("| ID | guard_reason | guard_category | latency_ms |")
        lines.append("|---|---|---|---:|")
        for c in fps:
            lines.append(
                f"| {c['id']} | {c['guard_reason']} | {c['guard_category']} | {c['latency_ms']:.3f} |"
            )

    lines += [
        "",
        "## 5. Conclusion",
        "",
        f"Quick-filter baseline results: detection_rate={detection*100:.1f}%, false_positive_rate={fp*100:.1f}%, audit_latency_p95_ms={p95:.3f}ms.",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    report = run_eval()

    from eval.runners._common import write_json_report

    write_json_report("output_audit_eval", report)

    md_main = _REPO_ROOT / "docs" / "evals" / "output-audit-eval-report.md"
    md_mirror = _REPO_ROOT / "docs" / "analysis" / "output_audit_eval_report.md"

    _write_md(report, md_main)
    _write_md(report, md_mirror)

    s = report["summary"]
    print("Output audit eval complete.")
    print(
        f"Detection rate: {s['detection_rate']*100:.1f}% | "
        f"False-positive rate: {s['false_positive_rate']*100:.1f}% | "
        f"Audit latency p95: {s['audit_latency_p95_ms']:.3f}ms"
    )
    print("Reports:")
    print(f"- {md_main}")
    print(f"- {md_mirror}")


if __name__ == "__main__":
    main()
