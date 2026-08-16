"""WS 阶段人话字段（Batch A · B-A3）。"""

from app.forge.phase_labels import phase_start_payload


def test_phase_start_payload_plan() -> None:
    p = phase_start_payload("plan")
    assert p["phase"] == "plan"
    assert "human_label" in p
    assert isinstance(p["eta_seconds"], int)
    assert p["eta_seconds"] > 0
