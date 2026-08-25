"""Unit tests for performance aggregation helpers (#117)."""

from eval.runners.performance_eval import (
    latency_degradation_pct,
    select_performance_subset,
    summarize_concurrency_batch,
    summarize_concurrency_levels,
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


def test_select_performance_subset_honors_ids_and_limit() -> None:
    generation = [
        {"id": "gen-001", "prompt": "a"},
        {"id": "gen-002", "prompt": "b"},
        {"id": "gen-003", "prompt": "c"},
    ]
    selected = select_performance_subset(
        generation,
        subset_ids=["gen-003", "gen-001", "missing"],
        limit=1,
    )
    assert [c["id"] for c in selected] == ["gen-003"]


def test_summarize_concurrency_batch_and_degradation() -> None:
    per_run = [
        {"success": True, "wall_clock_s": 100.0, "phases": []},
        {"success": True, "wall_clock_s": 120.0, "phases": []},
    ]
    batch = summarize_concurrency_batch(per_run, n=2, batch_wall_clock_s=180.0)
    assert batch["n"] == 2
    assert batch["success_rate"] == 1.0
    assert batch["throughput_per_hour"] == 40.0
    levels = [
        summarize_concurrency_batch(per_run, n=1, batch_wall_clock_s=240.0),
        batch,
        {
            "n": 3,
            "e2e_p95_s": 150.0,
            "success_rate": 1.0,
            "throughput_per_hour": 60.0,
        },
    ]
    levels[0]["e2e_p95_s"] = 100.0
    summary = summarize_concurrency_levels(levels)
    assert summary["latency_degradation_pct"] == 50.0
