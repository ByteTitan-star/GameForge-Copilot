"""Dimension 7: User preference persistence eval.

Issue: #124

Modes:
  - context_builder_baseline (default / CI): ContextBuilder injection formatting
  - live_api (--live / EVAL_PREF_LIVE=1): register → upsert → GET DB → conflict override
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
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
    setup_backend_path,
    status_cell,
    write_json_report,
    write_markdown,
)

setup_backend_path()
from app.forge.memory.context_builder import ContextBuilder  # noqa: E402


def _expected_keys(sc: dict[str, Any]) -> list[str]:
    return list(sc.get("expected_in_context") or sc.get("expected_in_prompt") or [])


def run_baseline() -> dict[str, Any]:
    scenarios = load_dataset("preference_scenarios.json")
    per_case: list[dict[str, Any]] = []
    injection_ok = 0
    explicit_ok = 0

    for sc in scenarios:
        prefs = [
            {
                "category": p["category"],
                "key": p["key"],
                "value_json": p["value_json"],
                "source": p["source"],
            }
            for p in sc["expected_preferences"]
        ]
        built = ContextBuilder.build(
            node="plan",
            current_input=sc["session2_prompt"],
            session_summary=None,
            recent_turns=[],
            preferences=prefs,
            artifacts=None,
            budget_tokens=4096,
        )
        body = built.user_message
        expected_keys = _expected_keys(sc)
        found = [
            k for k in expected_keys if k.split(".")[0] in body and k.split(".")[-1] in body
        ]
        explicit_count = sum(1 for p in prefs if p.get("source") == "explicit")
        case_ok = len(found) == len(expected_keys)
        if case_ok:
            injection_ok += 1
        if explicit_count == 0 or len(found) >= min(explicit_count, len(expected_keys) or explicit_count):
            explicit_ok += 1
        per_case.append(
            {
                "id": sc["id"],
                "mode": sc.get("mode", "explicit"),
                "expected_in_prompt": expected_keys,
                "found": found,
                "injection_ok": case_ok,
                "has_preferences_section": "Explicit Preferences" in body
                or "Inferred Preferences" in body,
            }
        )

    n = max(1, len(scenarios))
    return {
        "summary": {
            "scenario_count": len(scenarios),
            "cross_session_injection_rate": round(injection_ok / n, 4),
            "explicit_extraction_accuracy": round(explicit_ok / n, 4),
            "mode": "context_builder_baseline",
        },
        "per_case": per_case,
        "note": (
            "Baseline validates ContextBuilder injection formatting. "
            "Use --live for API/DB persistence checks."
        ),
    }


def _pref_match(items: list[dict[str, Any]], category: str, key: str) -> dict[str, Any] | None:
    for item in items:
        if item.get("category") == category and item.get("key") == key:
            return item
    return None


async def _register_and_login(client: Any) -> str:
    email = f"pref-eval-{uuid.uuid4().hex[:10]}@example.com"
    password = "password12345"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    code = ""
    for _ in range(20):
        peek = await client.get("/api/v1/dev/verification-code", params={"email": email})
        if peek.status_code == 200:
            code = str((peek.json().get("data") or {}).get("code") or "")
            if code:
                break
        await asyncio.sleep(0.2)
    if code:
        await client.post(
            "/api/v1/auth/verify-email", json={"email": email, "code": code}
        )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    if login.status_code != 200:
        raise RuntimeError(f"login failed: {login.status_code} {login.text[:200]}")
    token = (login.json().get("data") or {}).get("access_token")
    if not token:
        raise RuntimeError("missing access_token")
    return str(token)


async def _seed_inferred(
    user_id: uuid.UUID,
    *,
    category: str,
    key: str,
    value_json: dict[str, Any],
) -> None:
    from app.core.db import SessionLocal
    from app.forge.memory import preferences as pref_store

    async with SessionLocal() as db:
        await pref_store.upsert_preference(
            db,
            user_id=user_id,
            category=category,
            key=key,
            value_json=value_json,
            source="inferred",
            confidence=0.6,
        )
        await db.commit()


async def _me_user_id(client: Any) -> uuid.UUID:
    resp = await client.get("/api/v1/me/profile")
    if resp.status_code != 200:
        raise RuntimeError(f"profile failed: {resp.status_code}")
    data = resp.json().get("data") or {}
    return uuid.UUID(str(data.get("user_id") or data.get("id")))


async def _run_live_api(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    import httpx

    base = os.environ.get("EVAL_API_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("EVAL_API_BASE_URL required for preference live_api")

    limit = int(os.environ.get("EVAL_PREF_LIVE_LIMIT", "5"))
    cases = scenarios[:limit]
    per_case: list[dict[str, Any]] = []
    db_ok = 0
    conflict_ok = 0
    conflict_n = 0
    injection_ok = 0

    async with httpx.AsyncClient(base_url=base, timeout=60.0) as anon:
        token = await _register_and_login(anon)

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=60.0) as client:
        user_id = await _me_user_id(client)
        await client.delete("/api/v1/me/preferences")

        for sc in cases:
            mode = sc.get("mode", "explicit")
            await client.delete("/api/v1/me/preferences")
            case_result: dict[str, Any] = {"id": sc["id"], "mode": mode, "ok": False}

            try:
                if mode == "conflict":
                    conflict_n += 1
                    older = sc["conflict"]["older_implicit"]
                    newer = sc["conflict"]["newer_explicit"]
                    await _seed_inferred(
                        user_id,
                        category=older["category"],
                        key=older["key"],
                        value_json=older["value_json"],
                    )
                    put = await client.put(
                        "/api/v1/me/preferences",
                        json={
                            "category": newer["category"],
                            "key": newer["key"],
                            "value_json": newer["value_json"],
                        },
                    )
                    listed = await client.get("/api/v1/me/preferences")
                    items = (listed.json().get("data") or {}).get("items") or []
                    hit = _pref_match(items, newer["category"], newer["key"])
                    ok = (
                        put.status_code in {200, 201}
                        and hit is not None
                        and hit.get("source") == "explicit"
                        and hit.get("value_json") == newer["value_json"]
                    )
                    case_result["conflict_resolved"] = ok
                    if ok:
                        conflict_ok += 1
                        db_ok += 1
                    case_result["ok"] = ok
                else:
                    for pref in sc.get("expected_preferences") or []:
                        source = pref.get("source", "explicit")
                        if source == "inferred":
                            await _seed_inferred(
                                user_id,
                                category=pref["category"],
                                key=pref["key"],
                                value_json=pref["value_json"],
                            )
                        else:
                            put = await client.put(
                                "/api/v1/me/preferences",
                                json={
                                    "category": pref["category"],
                                    "key": pref["key"],
                                    "value_json": pref["value_json"],
                                },
                            )
                            if put.status_code not in {200, 201}:
                                raise RuntimeError(f"upsert failed: {put.text[:200]}")

                    listed = await client.get("/api/v1/me/preferences")
                    items = (listed.json().get("data") or {}).get("items") or []
                    missing = []
                    for pref in sc.get("expected_preferences") or []:
                        hit = _pref_match(items, pref["category"], pref["key"])
                        if hit is None:
                            missing.append(f"{pref['category']}.{pref['key']}")
                    ok = not missing
                    case_result["db_missing"] = missing
                    if ok:
                        db_ok += 1
                    case_result["ok"] = ok

                # Context injection check using expected prefs after DB write
                prefs_for_ctx = [
                    {
                        "category": p["category"],
                        "key": p["key"],
                        "value_json": p["value_json"],
                        "source": p.get("source", "explicit"),
                    }
                    for p in (sc.get("expected_preferences") or [])
                ]
                if mode == "conflict":
                    newer = sc["conflict"]["newer_explicit"]
                    prefs_for_ctx = [
                        {
                            "category": newer["category"],
                            "key": newer["key"],
                            "value_json": newer["value_json"],
                            "source": "explicit",
                        }
                    ]
                built = ContextBuilder.build(
                    node="plan",
                    current_input=sc["session2_prompt"],
                    session_summary=None,
                    recent_turns=[],
                    preferences=prefs_for_ctx,
                    artifacts=None,
                    budget_tokens=4096,
                )
                keys = _expected_keys(sc)
                found = [
                    k
                    for k in keys
                    if k.split(".")[0] in built.user_message
                    and k.split(".")[-1] in built.user_message
                ]
                inj = len(found) == len(keys)
                case_result["injection_ok"] = inj
                if inj:
                    injection_ok += 1
            except Exception as exc:  # noqa: BLE001
                case_result["error"] = f"{type(exc).__name__}:{exc}"
                case_result["ok"] = False

            per_case.append(case_result)

    n = max(1, len(cases))
    return {
        "summary": {
            "scenario_count": len(cases),
            "db_match_rate": round(db_ok / n, 4),
            "cross_session_injection_rate": round(injection_ok / n, 4),
            "preference_conflict_resolution": (
                round(conflict_ok / conflict_n, 4) if conflict_n else 1.0
            ),
            "mode": "live_api",
        },
        "per_case": per_case,
        "note": "Live API preference persistence against running backend + PostgreSQL.",
    }


def run_eval(*, live: bool = False) -> dict[str, Any]:
    if live:
        payload = asyncio.run(_run_live_api(load_dataset("preference_scenarios.json")))
    else:
        payload = run_baseline()

    report = base_report_meta(
        dimension="preference_persistence",
        runner="eval/runners/preference_eval.py",
        mode=payload["summary"]["mode"],
    )
    report["summary"] = payload["summary"]
    report["per_case"] = payload["per_case"]
    report["note"] = payload["note"]
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="User Preference Persistence Eval Report",
        summary=(
            f"Preference eval on **{s['scenario_count']}** scenarios "
            f"(mode={s['mode']})."
        ),
        runner="eval/runners/preference_eval.py",
        dataset="eval/datasets/preference_scenarios.json",
        dataset_count=s["scenario_count"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    if s["mode"] == "live_api":
        lines += [
            f"| db_match_rate | {s['db_match_rate']:.1%} | >= 95% | "
            f"{status_cell(s['db_match_rate'], 0.95, higher_is_better=True)} |",
            f"| cross_session_injection_rate | {s['cross_session_injection_rate']:.1%} | 100% | "
            f"{status_cell(s['cross_session_injection_rate'], 1.0, higher_is_better=True)} |",
            f"| preference_conflict_resolution | {s['preference_conflict_resolution']:.1%} | 100% | "
            f"{status_cell(s['preference_conflict_resolution'], 1.0, higher_is_better=True)} |",
        ]
    else:
        lines += [
            f"| cross_session_injection_rate | {s['cross_session_injection_rate']:.1%} | 100% | "
            f"{status_cell(s['cross_session_injection_rate'], 1.0, higher_is_better=True)} |",
            f"| explicit_extraction_accuracy | {s['explicit_extraction_accuracy']:.1%} | >= 95% | "
            f"{status_cell(s['explicit_extraction_accuracy'], 0.95, higher_is_better=True)} |",
        ]
    lines += ["", "## 7. Conclusion", "", report["note"], ""]
    below: list[str] = []
    if s.get("cross_session_injection_rate", 1) < 1.0:
        below.append("- cross_session_injection_rate below 100%")
    if s.get("db_match_rate") is not None and s["db_match_rate"] < 0.95:
        below.append("- db_match_rate below 95%")
    if s.get("preference_conflict_resolution", 1) < 1.0:
        below.append("- preference_conflict_resolution below 100%")
    lines.extend(below_target_section(below))
    return write_markdown(DOCS_EVALS_DIR / "preference-eval-report.md", lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preference persistence eval")
    parser.add_argument("--live", action="store_true", help="Run live API mode")
    args = parser.parse_args()
    # Do not inherit EVAL_LIVE from generation runs; use explicit flag/env.
    live = args.live or os.environ.get("EVAL_PREF_LIVE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    report = run_eval(live=live)
    json_path = write_json_report("preference_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"mode={s['mode']}")
    print(f"cross_session_injection_rate={s['cross_session_injection_rate']:.1%}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
