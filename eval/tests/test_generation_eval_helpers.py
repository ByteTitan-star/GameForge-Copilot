"""Unit tests for generation live-eval helpers."""

from eval.runners.generation_eval import (
    _build_telemetry_from_payloads,
    classify_terminal,
    hitl_decision_for,
)


def test_hitl_decision_map() -> None:
    assert hitl_decision_for("plan_confirm") == "approve"
    assert hitl_decision_for("art_confirm") == "select_a"
    assert hitl_decision_for("unknown") is None


def test_classify_terminal_success() -> None:
    ok, cat = classify_terminal(
        "done",
        artifact_gate={"generation_success": True, "previewable": True},
    )
    assert ok is True
    assert cat is None


def test_classify_terminal_done_without_artifact() -> None:
    ok, cat = classify_terminal("done", artifact_gate={"generation_success": False})
    assert ok is False
    assert cat == "done_without_artifact"


def test_classify_terminal_failed_and_timeout() -> None:
    ok, cat = classify_terminal("failed", artifact_gate=None)
    assert ok is False and cat == "run_failed"
    ok2, cat2 = classify_terminal("running", artifact_gate=None, timed_out=True)
    assert ok2 is False and cat2 == "timeout"


def test_build_telemetry_from_payloads_phases_qa_artifact() -> None:
    events = [
        {
            "type": "phase_start",
            "ts": "2026-08-21T10:00:00Z",
            "payload": {"phase": "plan"},
        },
        {
            "type": "phase_start",
            "ts": "2026-08-21T10:00:10Z",
            "payload": {"phase": "code"},
        },
        {
            "type": "qa_report",
            "ts": "2026-08-21T10:01:00Z",
            "payload": {
                "passed": False,
                "attempt": 1,
                "issues": ["TypeError: x is undefined"],
                "log_excerpt": "TypeError: x is undefined",
                "failure_kind": "runtime",
            },
        },
        {
            "type": "phase_start",
            "ts": "2026-08-21T10:01:40Z",
            "payload": {"phase": "playtest"},
        },
        {
            "type": "qa_report",
            "ts": "2026-08-21T10:01:50Z",
            "payload": {
                "passed": True,
                "attempt": 2,
                "issues": [],
                "log_excerpt": "",
            },
        },
        {"type": "done", "ts": "2026-08-21T10:02:00Z", "payload": {}},
    ]
    game = {"current_version": 1}
    terminal = {
        "artifact_gate": {
            "generation_success": True,
            "previewable": True,
        }
    }
    telem = _build_telemetry_from_payloads(
        events, messages=[], game=game, terminal=terminal
    )
    by_name = {p["name"]: p["duration_s"] for p in telem["phases"]}
    assert by_name["plan"] == 10.0
    assert by_name["code"] == 90.0
    assert telem["qa"]["attempts"] == 2
    assert telem["qa"]["first_pass"] is False
    assert telem["qa"]["final_pass"] is True
    assert telem["qa"]["repair_rounds"] == 1
    assert "runtime" in telem["qa"]["error_categories"]
    assert telem["artifact"]["current_version"] == 1
    assert telem["artifact"]["previewable"] is True
    assert telem["artifact"]["generation_success"] is True
    assert telem["artifact"]["empty_or_trivial"] is False
