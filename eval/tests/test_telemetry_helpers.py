# eval/tests/test_telemetry_helpers.py
from eval.runners.telemetry import (
    aggregate_phases,
    classify_qa_error,
    derive_qa_metrics,
    is_empty_or_trivial_html,
)


def test_aggregate_phases_from_phase_start_events() -> None:
    events = [
        {"type": "phase_start", "ts": "2026-08-21T10:00:00Z", "payload": {"phase": "plan"}},
        {"type": "phase_start", "ts": "2026-08-21T10:00:10Z", "payload": {"phase": "code"}},
        {"type": "phase_start", "ts": "2026-08-21T10:01:40Z", "payload": {"phase": "playtest"}},
        {"type": "done", "ts": "2026-08-21T10:02:00Z", "payload": {}},
    ]
    phases = aggregate_phases(events)
    by_name = {p["name"]: p["duration_s"] for p in phases}
    assert by_name["plan"] == 10.0
    assert by_name["code"] == 90.0
    assert by_name["playtest"] == 20.0


def test_classify_qa_error_keywords() -> None:
    assert classify_qa_error("SyntaxError: unexpected token") == "syntax"
    assert classify_qa_error("TypeError: x is undefined") == "runtime"
    assert classify_qa_error("canvas is blank / screenshot mismatch") == "visual"
    assert classify_qa_error("playtest timed out after 60s") == "timeout"
    assert classify_qa_error("sandbox infra unavailable") == "infra"
    assert classify_qa_error("something odd") == "unknown"


def test_derive_qa_metrics_repair_round() -> None:
    qa = derive_qa_metrics(
        attempts=2,
        first_playtest_ok=False,
        final_playtest_ok=True,
        error_categories=["runtime"],
    )
    assert qa["attempts"] == 2
    assert qa["first_pass"] is False
    assert qa["final_pass"] is True
    assert qa["repair_rounds"] == 1


def test_derive_qa_metrics_first_pass_zero_repairs() -> None:
    qa = derive_qa_metrics(
        attempts=3,
        first_playtest_ok=True,
        final_playtest_ok=True,
        error_categories=["syntax", "runtime"],
    )
    assert qa["first_pass"] is True
    assert qa["repair_rounds"] == 0
    assert qa["error_categories"] == ["syntax", "runtime"]


def test_empty_or_trivial_html() -> None:
    assert is_empty_or_trivial_html("") is True
    assert is_empty_or_trivial_html("<html><body></body></html>") is True
    assert is_empty_or_trivial_html("<html><body><canvas id='g'></canvas><script>boot()</script></body></html>") is False


def test_empty_html_short_without_canvas_or_script() -> None:
    assert is_empty_or_trivial_html("<p>x</p>") is True
