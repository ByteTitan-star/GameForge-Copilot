"""Native code_qa 集成测试（mock LLM）。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.enums import RunStatus
from app.forge import code_qa_exec as cqe
from app.forge.code_qa_exec import execute_code_or_repair
from app.forge.native.codegen import READY_SIGNAL
from app.hosting import store


def _valid_main_gd() -> str:
    return f'''extends Node2D

func _ready() -> void:
\tprint("{READY_SIGNAL}")
'''


@pytest.mark.asyncio
async def test_execute_code_or_repair_godot_materializes_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "native_engine_enabled", True)
    monkeypatch.setattr(settings, "hosting_root", str(tmp_path / "hosting"))
    monkeypatch.setattr(settings, "memory_session_summary", False)

    game_id = __import__("uuid").uuid4()
    run_id = __import__("uuid").uuid4()

    async def _fake_code_llm(_ctx, _system, _user, **kwargs) -> tuple[str, bool]:
        payload = {
            "format": "godot-project",
            "files": {"scenes/main.gd": _valid_main_gd()},
        }
        return json.dumps(payload), False

    async def _fake_build_context(*_a, **_k):
        return SimpleNamespace(user_message="按设计稿实现游戏")

    monkeypatch.setattr(cqe, "_code_llm", _fake_code_llm)
    monkeypatch.setattr(
        "app.forge.memory.loader.build_node_context",
        _fake_build_context,
    )

    committed: dict = {}

    async def _commit_native(_ctx, **kwargs) -> dict:
        committed.update(kwargs)
        version = 1
        await store.write_native_artifact(game_id, version, kwargs["files"])
        return {
            "code_ok": True,
            "candidate_ready": True,
            "candidate_version": version,
            "candidate_kind": "native-godot",
            "design_doc": kwargs["design_doc"],
            "artifacts": kwargs["artifacts"],
            "art_direction": kwargs["art_direction"],
        }

    ctx = SimpleNamespace(
        game=SimpleNamespace(
            id=game_id,
            title="Test: 测试",
            owner_id=game_id,
            current_version=0,
        ),
        run=SimpleNamespace(id=run_id, status=RunStatus.RUNNING.value, ended_at=None),
        s=SimpleNamespace(refresh=AsyncMock(), commit=AsyncMock()),
        r=None,
    )

    state = {
        "design_doc": {
            "title": "Test: 测试",
            "engine": {"id": "godot4", "rationale": "2D native", "version": "4.3"},
        },
        "artifacts": [],
        "art_direction": {},
        "attempt": 0,
    }

    out = await execute_code_or_repair(
        ctx,
        state,
        streamed_llm=AsyncMock(),
        set_phase=AsyncMock(),
        check_ctrl=AsyncMock(return_value="ok"),
        normalize_html=lambda x: x,
        commit_project_build=AsyncMock(),
        commit_native_build=_commit_native,
        run_finalized_exc=RuntimeError,
    )

    assert out["candidate_ready"] is True
    assert out["candidate_kind"] == "native-godot"
    assert committed["files"]["project.godot"]
    artifact_dir = store.artifact_dir(game_id, 1)
    assert (artifact_dir / "project.godot").is_file()
    assert (artifact_dir / "scenes" / "main.gd").is_file()
