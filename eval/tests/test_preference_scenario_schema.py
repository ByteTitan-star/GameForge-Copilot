"""Schema checks for preference_scenarios.json (#124)."""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED = {"id", "session2_prompt", "expected_preferences"}


def test_preference_scenarios_min_shape() -> None:
    raw = json.loads(
        Path("eval/datasets/preference_scenarios.json").read_text(encoding="utf-8")
    )
    assert len(raw) >= 15
    modes: set[str] = set()
    for row in raw:
        assert REQUIRED <= set(row)
        mode = row.get("mode", "explicit")
        modes.add(mode)
        if mode == "conflict":
            assert row.get("conflict")
            assert "older_implicit" in row["conflict"]
            assert "newer_explicit" in row["conflict"]
    assert "implicit" in modes
    assert "conflict" in modes
