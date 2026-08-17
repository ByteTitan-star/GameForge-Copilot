"""P5 cleanup：正式 Node 不得再保留 use_context_builder 双路径 concat。"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3] / "app" / "forge"
_TARGETS = (
    _ROOT / "graph.py",
    _ROOT / "code_qa_exec.py",
)


def test_no_legacy_context_builder_gate_in_compose_paths() -> None:
    forbidden = (
        "if not use_context_builder()",
        "if use_context_builder():",
    )
    for path in _TARGETS:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path.name} still gates on {needle!r}"
        assert "build_node_context" in text
