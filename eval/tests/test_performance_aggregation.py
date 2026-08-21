"""Unit tests for performance aggregation helpers (#117)."""

from eval.runners.performance_eval import (
    latency_degradation_pct,
    summarize_phase_latencies,
    throughput_per_hour,
)


def test_latency_degradation_pct() -> None:
    assert latency_degradation_pct(p95_n1=100.0, p95_n3=150.0) == 50.0


def test_throughput_per_hour() -> None:
    assert throughput_per_hour(successes=10, wall_clock_s=1800.0) == 20.0


def test_summarize_phase_latencies() -> None:
    per_run = [
        {
            "wall_clock_s": 100.0,
            "phases": [
                {"name": "plan", "duration_s": 10.0},
                {"name": "code", "duration_s": 70.0},
            ],
        },
        {
            "wall_clock_s": 200.0,
            "phases": [
                {"name": "plan", "duration_s": 20.0},
                {"name": "code", "duration_s": 120.0},
            ],
        },
    ]
    s = summarize_phase_latencies(per_run)
    assert s["e2e_p50_s"] == 100.0
    # Existing percentile helper: idx = int(p * (n-1)); for n=2, p95 → index 0
    assert s["e2e_p95_s"] == 100.0
    assert s["plan_latency_p50_s"] == 10.0
    assert s["code_gen_latency_p50_s"] == 70.0
