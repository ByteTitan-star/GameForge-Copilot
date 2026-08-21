"""Dimension 1: Generation success rate eval.

Issue: #115

Modes:
  - offline (default): validate dataset + emit readiness report
  - live: requires EVAL_LIVE=1, EVAL_API_BASE_URL, EVAL_ACCESS_TOKEN
    Creates game + run, auto-resolves HITL, polls until done/failed/timeout.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
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
from eval.runners.telemetry import (
    aggregate_phases,
    classify_qa_error,
    derive_qa_metrics,
    is_empty_or_trivial_html,
)

# HITL auto-resolve map for unattended agent eval.
_HITL_DECISION: dict[str, str] = {
    "plan_confirm": "approve",
    "art_confirm": "select_a",
    "sandbox_failed": "approve",
    "qa_failed": "approve",
}


def hitl_decision_for(node: str) -> str | None:
    return _HITL_DECISION.get(node)


def classify_terminal(
    status: str,
    *,
    artifact_gate: dict[str, Any] | None,
    timed_out: bool = False,
) -> tuple[bool, str | None]:
    """Return (success, failure_category)."""
    if timed_out:
        return False, "timeout"
    if status == "failed":
        return False, "run_failed"
    if status == "done":
        gate = artifact_gate or {}
        if gate.get("generation_success") or gate.get("previewable"):
            return True, None
        return False, "done_without_artifact"
    return False, "unexpected_status"


def _event_type_name(event: dict[str, Any]) -> str:
    raw = event.get("type", "")
    return str(getattr(raw, "value", raw)).lower()


def _qa_reports_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for event in events:
        if _event_type_name(event) != "qa_report":
            continue
        payload = event.get("payload") or {}
        if isinstance(payload, dict):
            reports.append(payload)
    return reports


def _error_categories_from_qa(reports: list[dict[str, Any]]) -> list[str]:
    cats: list[str] = []
    seen: set[str] = set()
    for report in reports:
        if report.get("passed"):
            continue
        chunks = [
            str(report.get("failure_kind") or ""),
            str(report.get("log_excerpt") or ""),
            " ".join(str(x) for x in (report.get("issues") or [])),
        ]
        cat = classify_qa_error(" ".join(chunks))
        if cat not in seen:
            seen.add(cat)
            cats.append(cat)
    return cats


def _html_snippet_from_messages(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(messages):
        content = str(message.get("content") or "")
        if "<html" in content.lower() or "<canvas" in content.lower():
            return content
    return None


def _build_telemetry_from_payloads(
    events: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    game: dict[str, Any],
    terminal: dict[str, Any],
) -> dict[str, Any]:
    """Derive phases/qa/artifact from harvested API payloads (pure, testable)."""
    phases = aggregate_phases(events)
    reports = _qa_reports_from_events(events)
    attempts = 0
    for report in reports:
        try:
            attempts = max(attempts, int(report.get("attempt") or 0))
        except (TypeError, ValueError):
            continue
    if attempts == 0 and reports:
        attempts = len(reports)

    first_pass = bool(reports[0].get("passed")) if reports else False
    final_pass = bool(reports[-1].get("passed")) if reports else bool(
        (terminal.get("artifact_gate") or {}).get("generation_success")
        or (terminal.get("artifact_gate") or {}).get("previewable")
    )
    qa = derive_qa_metrics(
        attempts=attempts,
        first_playtest_ok=first_pass,
        final_playtest_ok=final_pass,
        error_categories=_error_categories_from_qa(reports),
    )

    gate = terminal.get("artifact_gate") or {}
    html = _html_snippet_from_messages(messages)
    empty = is_empty_or_trivial_html(html) if html is not None else False
    try:
        current_version = int(game.get("current_version") or 0)
    except (TypeError, ValueError):
        current_version = 0

    artifact = {
        "current_version": current_version,
        "previewable": bool(gate.get("previewable")),
        "generation_success": bool(gate.get("generation_success")),
        "empty_or_trivial": empty,
    }
    return {"phases": phases, "qa": qa, "artifact": artifact}


async def _harvest_run_telemetry(
    client: Any,
    *,
    game_id: str,
    run_id: str,
    terminal: dict[str, Any],
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    game: dict[str, Any] = {}
    try:
        events_resp = await client.get(f"/api/v1/runs/{run_id}/events")
        if events_resp.status_code == 200:
            events = list(events_resp.json().get("data") or [])
    except Exception:  # noqa: BLE001
        events = []
    try:
        msgs_resp = await client.get(f"/api/v1/games/{game_id}/messages")
        if msgs_resp.status_code == 200:
            messages = list(msgs_resp.json().get("data") or [])
    except Exception:  # noqa: BLE001
        messages = []
    try:
        game_resp = await client.get(f"/api/v1/games/{game_id}")
        if game_resp.status_code == 200:
            game = dict(game_resp.json().get("data") or {})
    except Exception:  # noqa: BLE001
        game = {}
    return _build_telemetry_from_payloads(events, messages, game, terminal)


def _validate_dataset(dataset: list[dict[str, Any]]) -> dict[str, Any]:
    by_complexity = Counter(c.get("complexity", "unknown") for c in dataset)
    return {
        "total": len(dataset),
        "simple": by_complexity.get("simple", 0),
        "medium": by_complexity.get("medium", 0),
        "hard": by_complexity.get("hard", 0),
        "valid": len(dataset) >= 50,
    }


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


async def _auto_resolve_hitl(
    client: Any,
    *,
    game_id: str,
    run_id: str,
    node: str,
) -> bool:
    decision = hitl_decision_for(node)
    if not decision:
        return False
    resp = await client.post(
        f"/api/v1/games/{game_id}/runs/{run_id}/hitl/resolve",
        json={"node": node, "decision": decision},
    )
    return resp.status_code in {200, 201}


async def _poll_run(
    client: Any,
    *,
    game_id: str,
    run_id: str,
    timeout_s: float,
    poll_interval_s: float,
    max_hitl: int,
) -> dict[str, Any]:
    started = time.monotonic()
    hitl_count = 0
    last: dict[str, Any] = {}

    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout_s:
            return {
                "status": last.get("status", "running"),
                "phase": last.get("phase"),
                "artifact_gate": last.get("artifact_gate"),
                "pause_reason": last.get("pause_reason"),
                "hitl_resolves": hitl_count,
                "wall_clock_s": round(elapsed, 1),
                "timed_out": True,
            }

        try:
            resp = await client.get(f"/api/v1/runs/{run_id}")
        except Exception as exc:  # noqa: BLE001 — transient network during long polls
            print(f"[live] poll transport error: {type(exc).__name__}", flush=True)
            await asyncio.sleep(poll_interval_s)
            continue

        if resp.status_code != 200:
            await asyncio.sleep(poll_interval_s)
            continue

        data = resp.json().get("data") or {}
        last = data
        status = data.get("status")

        if status in {"done", "failed"}:
            return {
                "status": status,
                "phase": data.get("phase"),
                "artifact_gate": data.get("artifact_gate"),
                "pause_reason": data.get("pause_reason"),
                "hitl_resolves": hitl_count,
                "wall_clock_s": round(time.monotonic() - started, 1),
                "timed_out": False,
            }

        if status == "paused":
            hitl = data.get("current_hitl") or {}
            wait = data.get("hitl_wait") or {}
            node = hitl.get("node") or wait.get("node")
            pause_reason = data.get("pause_reason")

            if node and hitl_count < max_hitl:
                try:
                    ok = await _auto_resolve_hitl(
                        client, game_id=game_id, run_id=run_id, node=node
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"[live] hitl resolve error: {type(exc).__name__}", flush=True)
                    ok = False
                if ok:
                    hitl_count += 1
                    print(f"[live] auto-HITL {node} ok (#{hitl_count})", flush=True)
                    await asyncio.sleep(poll_interval_s)
                    continue

            if pause_reason == "recoverable_error":
                try:
                    retry = await client.post(f"/api/v1/runs/{run_id}/retry")
                    if retry.status_code in {200, 201}:
                        print("[live] issued /retry for recoverable_error", flush=True)
                        await asyncio.sleep(poll_interval_s)
                        continue
                except Exception as exc:  # noqa: BLE001
                    print(f"[live] retry error: {type(exc).__name__}", flush=True)

            # Stuck pause — treat as failure after one more poll window.
            await asyncio.sleep(poll_interval_s)
            try:
                stuck = await client.get(f"/api/v1/runs/{run_id}")
                stuck_data = (
                    (stuck.json().get("data") or {}) if stuck.status_code == 200 else data
                )
            except Exception:  # noqa: BLE001
                stuck_data = data
            if stuck_data.get("status") == "paused":
                return {
                    "status": "paused",
                    "phase": stuck_data.get("phase"),
                    "artifact_gate": stuck_data.get("artifact_gate"),
                    "pause_reason": stuck_data.get("pause_reason"),
                    "hitl_node": node,
                    "hitl_resolves": hitl_count,
                    "wall_clock_s": round(time.monotonic() - started, 1),
                    "timed_out": False,
                    "stuck_pause": True,
                }

        await asyncio.sleep(poll_interval_s)


async def _create_run_with_retry(
    client: Any,
    *,
    game_id: str,
    prompt: str,
    create_lock: asyncio.Lock,
    max_attempts: int = 40,
) -> Any:
    """Serialize + retry create_run.

    Backend holds a per-user Redis lock during create (anti double-submit) and
    rejects with 429 when active runs >= MAX_CONCURRENT_RUNS. Parallel eval
    must not treat the lock collision as a hard failure.
    """
    last: Any = None
    for attempt in range(1, max_attempts + 1):
        async with create_lock:
            last = await client.post(
                f"/api/v1/games/{game_id}/runs",
                json={"requirement": prompt},
            )
        if last.status_code in {200, 201}:
            return last
        if last.status_code != 429:
            return last
        # Slot full or create-lock busy: wait and retry outside the lock.
        await asyncio.sleep(min(0.5 * attempt, 5.0))
        print(
            f"[live] create_run 429 retry {attempt}/{max_attempts} game={game_id[:8]}…",
            flush=True,
        )
    return last


async def _run_one_case(
    client: Any,
    case: dict[str, Any],
    *,
    timeout_s: float,
    poll_interval_s: float,
    max_hitl: int,
    create_lock: asyncio.Lock,
) -> dict[str, Any]:
    prompt = case["prompt"]
    # Match ForgePage.startGeneration: title = requirement[:24]
    create = await client.post(
        "/api/v1/games",
        json={"title": (prompt[:24] or f"eval-{case['id']}"), "requirement": prompt},
    )
    if create.status_code not in {200, 201}:
        return {
            "id": case["id"],
            "prompt": prompt,
            "complexity": case["complexity"],
            "success": False,
            "status_code": create.status_code,
            "failure_category": "create_game_error",
            "detail": create.text[:300],
        }

    game_id = create.json()["data"]["game_id"]
    run_resp = await _create_run_with_retry(
        client, game_id=game_id, prompt=prompt, create_lock=create_lock
    )
    if run_resp.status_code not in {200, 201}:
        return {
            "id": case["id"],
            "prompt": prompt,
            "complexity": case["complexity"],
            "success": False,
            "game_id": game_id,
            "status_code": run_resp.status_code,
            "failure_category": "create_run_error",
            "detail": run_resp.text[:300],
        }

    run_id = run_resp.json()["data"]["run_id"]
    terminal = await _poll_run(
        client,
        game_id=game_id,
        run_id=run_id,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
        max_hitl=max_hitl,
    )

    if terminal.get("stuck_pause"):
        success, category = False, "stuck_hitl"
    else:
        success, category = classify_terminal(
            str(terminal.get("status") or ""),
            artifact_gate=terminal.get("artifact_gate"),
            timed_out=bool(terminal.get("timed_out")),
        )

    # Real UI treats current_version>=1 as playable; gate may be cleared after done.
    if (
        not success
        and str(terminal.get("status") or "") == "done"
        and category == "done_without_artifact"
    ):
        try:
            detail = await client.get(f"/api/v1/games/{game_id}")
            if detail.status_code == 200:
                ver = int((detail.json().get("data") or {}).get("current_version") or 0)
                if ver >= 1:
                    success, category = True, None
                    terminal["artifact_gate"] = {
                        **(terminal.get("artifact_gate") or {}),
                        "generation_success": True,
                        "previewable": True,
                        "current_version": ver,
                    }
        except Exception:  # noqa: BLE001
            pass

    error_detail: str | None = None
    if not success:
        try:
            msgs = await client.get(f"/api/v1/games/{game_id}/messages")
            if msgs.status_code == 200:
                for m in reversed(msgs.json().get("data") or []):
                    if m.get("kind") in {"failed", "error", "system"}:
                        error_detail = str(m.get("content") or "")[:400]
                        break
        except Exception:  # noqa: BLE001
            error_detail = None

    telemetry = await _harvest_run_telemetry(
        client, game_id=game_id, run_id=run_id, terminal=terminal
    )

    return {
        "id": case["id"],
        "prompt": prompt,
        "complexity": case["complexity"],
        "success": success,
        "game_id": game_id,
        "run_id": run_id,
        "status": terminal.get("status"),
        "phase": terminal.get("phase"),
        "artifact_gate": terminal.get("artifact_gate"),
        "hitl_resolves": terminal.get("hitl_resolves"),
        "wall_clock_s": terminal.get("wall_clock_s"),
        "failure_category": category,
        "error_detail": error_detail,
        "phases": telemetry.get("phases") or [],
        "qa": telemetry.get("qa") or {},
        "artifact": telemetry.get("artifact") or {},
    }


async def _run_live(dataset: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    import httpx

    base = os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")
    token = os.environ.get("EVAL_ACCESS_TOKEN", "")
    if not base or not token:
        raise RuntimeError("EVAL_API_BASE_URL and EVAL_ACCESS_TOKEN required for live mode")

    timeout_s = _env_float("EVAL_RUN_TIMEOUT_S", 900.0)
    poll_interval_s = _env_float("EVAL_POLL_INTERVAL_S", 5.0)
    max_hitl = _env_int("EVAL_MAX_HITL", 8)
    # Cap to platform per-user MAX_CONCURRENT_RUNS (default 3); higher → RATE_LIMITED.
    concurrency = max(1, _env_int("EVAL_CONCURRENCY", 3))
    headers = {"Authorization": f"Bearer {token}"}
    cases = dataset[:limit]
    per_run: list[dict[str, Any] | None] = [None] * len(cases)
    sem = asyncio.Semaphore(concurrency)
    create_lock = asyncio.Lock()

    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=120.0) as client:

        async def _bounded(idx: int, case: dict[str, Any]) -> None:
            async with sem:
                print(
                    f"[live] starting {case['id']} ({case.get('complexity')}) "
                    f"slot={concurrency}...",
                    flush=True,
                )
                result = await _run_one_case(
                    client,
                    case,
                    timeout_s=timeout_s,
                    poll_interval_s=poll_interval_s,
                    max_hitl=max_hitl,
                    create_lock=create_lock,
                )
                print(
                    f"[live] {case['id']} success={result['success']} "
                    f"status={result.get('status')} category={result.get('failure_category')} "
                    f"wall={result.get('wall_clock_s')}s",
                    flush=True,
                )
                per_run[idx] = result

        await asyncio.gather(*[_bounded(i, c) for i, c in enumerate(cases)])

    return [r for r in per_run if r is not None]


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
        by_cat = Counter(r.get("failure_category") or "ok" for r in per_run)
        summary = {
            "prompts_run": len(per_run),
            "success_rate": round(successes / n, 4),
            "failure_categories": dict(by_cat),
            "mode": "live_agent",
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


def _prompt_index() -> dict[str, str]:
    return {c["id"]: str(c.get("prompt") or "") for c in load_dataset("generation.json")}


def _case_table_lines(per_run: list[dict[str, Any]]) -> list[str]:
    """Document which cases were evaluated and their outcomes."""
    if not per_run:
        return []
    prompts = _prompt_index()
    lines = [
        "",
        "### Evaluated cases",
        "",
        "| Case | Complexity | Prompt | Result | Wall (s) | HITL |",
        "|------|------------|--------|--------|----------|------|",
    ]
    for r in per_run:
        cid = str(r.get("id") or "")
        prompt = str(r.get("prompt") or prompts.get(cid) or "").replace("|", "\\|")
        if len(prompt) > 72:
            prompt = prompt[:69] + "..."
        ok = "✅" if r.get("success") else "❌"
        wall = r.get("wall_clock_s")
        wall_s = f"{wall:.1f}" if isinstance(wall, (int, float)) else "—"
        hitl = r.get("hitl_resolves")
        hitl_s = str(hitl) if hitl is not None else "—"
        lines.append(
            f"| `{cid}` | {r.get('complexity', '—')} | {prompt} | {ok} | {wall_s} | {hitl_s} |"
        )
    walls = [float(r["wall_clock_s"]) for r in per_run if isinstance(r.get("wall_clock_s"), (int, float))]
    if walls:
        lines += [
            "",
            f"- Mean wall-clock: **{sum(walls) / len(walls):.1f}s** "
            f"(min {min(walls):.1f}s / max {max(walls):.1f}s)",
        ]
    by_cx = Counter(str(r.get("complexity") or "unknown") for r in per_run)
    ok_by_cx = Counter(
        str(r.get("complexity") or "unknown") for r in per_run if r.get("success")
    )
    lines += ["", "### Per-complexity", "", "| Complexity | Run | Success | Rate |", "|------------|-----|---------|------|"]
    for cx, n in sorted(by_cx.items()):
        ok = ok_by_cx.get(cx, 0)
        lines.append(f"| {cx} | {n} | {ok} | {ok / n:.1%} |")
    return lines


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    v = report["dataset_validation"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    mode = s["mode"]
    per_run = list(report.get("per_run") or [])

    if mode == "offline_readiness":
        summary_text = (
            f"Dataset validation: **{v['total']}** prompts "
            f"({v['simple']} simple / {v['medium']} medium / {v['hard']} hard). "
            "Live generation not executed."
        )
    else:
        if per_run:
            n_ok = sum(1 for r in per_run if r.get("success"))
            summary_text = (
                f"Live agent run on **{s['prompts_run']}** prompts "
                f"(`{per_run[0]['id']}`–`{per_run[-1]['id']}` from "
                f"`eval/datasets/generation.json`). "
                f"Success rate: **{s['success_rate']:.1%}** ({n_ok}/{len(per_run)})."
            )
        else:
            summary_text = (
                f"Live agent run on **{s['prompts_run']}** prompts. "
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
            f"| prompts_run | {s.get('prompts_run', len(per_run))} | — | — |",
        ]
        cats = s.get("failure_categories") or {}
        if cats:
            lines += ["", "### Failure categories", ""]
            for k, n in sorted(cats.items()):
                lines.append(f"- `{k}`: {n}")
        lines.extend(_case_table_lines(per_run))
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
        lines.append(
            "Live agent evaluation complete (create game → run → auto-HITL → terminal status). "
            "Success = `done` and playable artifact (`generation_success` / `previewable` / "
            "`current_version >= 1`)."
        )
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
    parser.add_argument("--limit", type=int, default=10, help="Live prompt limit")
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
