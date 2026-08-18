"""P4：Capability Precheck — 结构化校验，禁止关键词黑名单。"""

from __future__ import annotations

import json
import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.core.config import settings
from app.enums import FailureClass
from app.forge.capability import capability_conflicts, developability_precheck
from app.forge.design_doc import parse_design_doc
from app.forge.failure import classify_failure


def _doc_with_caps(**caps: object) -> dict:
    from tests.conftest import _valid_design_doc_json

    doc = parse_design_doc(_valid_design_doc_json(), "T")
    doc["required_capabilities"] = {
        "renderer": "canvas2d",
        "physics_2d": False,
        "realtime_multiplayer": False,
        "backend_server": False,
        "webgl_3d": False,
        **caps,
    }
    return doc


def test_gameplay_mentioning_3d_is_not_capability_mismatch() -> None:
    doc = _doc_with_caps()
    doc["gameplay"] = "不要使用 3D、物理引擎或网络同步，只做 2D 单机。"
    assert capability_conflicts(doc) == []
    classified = classify_failure(errors=[doc["gameplay"]])
    assert classified.failure_class != FailureClass.CAPABILITY_MISMATCH


def test_realtime_multiplayer_conflict_is_explainable() -> None:
    conflicts = capability_conflicts(_doc_with_caps(realtime_multiplayer=True))
    assert conflicts
    joined = " ".join(conflicts)
    assert "realtime_multiplayer" in joined
    assert "CapabilityProfile" in joined


def test_unsupported_renderer_conflict_is_explainable() -> None:
    conflicts = capability_conflicts(_doc_with_caps(renderer="webgl3d", webgl_3d=True))
    assert conflicts
    joined = " ".join(conflicts)
    assert "renderer" in joined or "webgl_3d" in joined


def test_supported_canvas2d_has_no_conflicts() -> None:
    assert capability_conflicts(_doc_with_caps()) == []
    assert developability_precheck(_doc_with_caps()) == []


async def test_capability_mismatch_detected_before_plan_confirm(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.enums import LLMProvider
    from app.forge.runner import execute_run
    from app.llm.provider import LLMCompletion, Usage
    from tests.conftest import _valid_design_doc_json

    doc = json.loads(_valid_design_doc_json())
    doc["required_capabilities"] = {
        "renderer": "canvas2d",
        "realtime_multiplayer": True,
        "backend_server": False,
        "physics_2d": False,
        "webgl_3d": False,
    }
    payload = json.dumps(doc, ensure_ascii=False)

    async def _mismatch(_db, _r, _user_id, _config_id, system, _user_msg, **_kwargs):
        if "策划" in system or "JSON" in system:
            return LLMCompletion(content=payload, usage=Usage(10, 5)), LLMProvider.ANTHROPIC
        return LLMCompletion(content="ok", usage=Usage(1, 1)), LLMProvider.ANTHROPIC

    monkeypatch.setattr("app.llm.client.call_llm", _mismatch)
    monkeypatch.setattr("app.forge.graph.PLAN_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(settings, "stream_enabled", False)

    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "Cap P4", "requirement": "联机对战"}
            )
        ).json()["data"]["game_id"]
    )
    rid = uuid.UUID(
        (await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()[
            "data"
        ]["run_id"]
    )
    await execute_run({"redis": redis_client}, rid)

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    data = r.json()["data"]
    hitl = data.get("current_hitl") or {}
    assert hitl.get("node") != "plan_confirm"
