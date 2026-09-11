"""C 级视觉验收（#160）：解析/降级/warning 构造单测 + execute_playtest 钩子集成测试。"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

from app.forge import visual_acceptance as va

_VERDICT = {
    "observed": {"background": "dark", "summary": "dark screen, button on right"},
    "match": False,
    "confidence": 0.9,
    "issues": [
        {
            "kind": "layout",
            "severity": "high",
            "detail": "START button is right-aligned, brief asks left",
        },
        {"kind": "theme", "severity": "low", "detail": "palette slightly warmer than brief"},
    ],
}


# ---------------- parse / format 单测 ----------------


def test_parse_verdict_plain_and_fenced() -> None:
    raw = json.dumps(_VERDICT)
    assert va.parse_verdict(raw) is not None
    fenced = f"```json\n{raw}\n```"
    assert va.parse_verdict(fenced) == va.parse_verdict(raw)


def test_parse_verdict_normalizes_bad_fields() -> None:
    out = va.parse_verdict(
        json.dumps(
            {
                "match": "false",  # 字符串布尔
                "confidence": 7,  # 越界 → clamp
                "issues": [
                    {"kind": "weird", "severity": "huge", "detail": "x"},  # 归一
                    {"kind": "theme", "severity": "low"},  # 无 detail → 丢弃
                    "garbage",  # 非 dict → 丢弃
                ],
            }
        )
    )
    assert out is not None
    assert out["match"] is False
    assert out["confidence"] == 1.0
    assert out["issues"] == [{"kind": "style", "severity": "low", "detail": "x"}]


@pytest.mark.parametrize("bad", ["", "not json", "[1,2]", '{"no_match": true}'])
def test_parse_verdict_rejects_bad_output(bad: str) -> None:
    assert va.parse_verdict(bad) is None


def test_warning_lines_variants() -> None:
    assert va.warning_lines(None) == []
    assert va.warning_lines({**_VERDICT, "match": True}) == []
    lines = va.warning_lines(_VERDICT)
    assert lines[0] == "[layout/high] START button is right-aligned, brief asks left"
    # match=false 但无 issues → observed 摘要兜底
    fallback = va.warning_lines({"match": False, "issues": [], "observed": {"summary": "light UI"}})
    assert fallback == ["[style/low] render does not match the design brief: light UI"]


def test_visual_warning_block_for_repair_prompt() -> None:
    assert va.visual_warning_block({}) == ""
    block = va.visual_warning_block({"visual_warnings": ["[layout/high] button on the wrong side"]})
    assert block.startswith("【视觉验收警告")
    assert "- [layout/high] button on the wrong side" in block


def test_build_visual_brief_keeps_visible_intent_and_clips() -> None:
    doc = {
        "title": "Space Runner",
        "presentation": {"visual_style": "dark neon, bright accents"},
        "overview": {"genre": "arcade runner"},
    }
    brief = va.build_visual_brief(doc, {"palette": ["#111", "#f4c542"]})
    assert "Space Runner" in brief and "dark neon" in brief and "arcade runner" in brief
    long_brief = va.build_visual_brief(doc, {"blob": "x" * 2000})
    assert len(long_brief) < 1200  # art_direction 序列化被裁剪


# ---------------- evaluate 降级与调用形状 ----------------


async def test_evaluate_skips_when_unconfigured(db_session, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "visual_acceptance_model", "")
    monkeypatch.setattr(settings, "visual_acceptance_apikey", "")
    assert await va.evaluate_visual_acceptance(db_session, b"png", {}, {}) is None


def _configure_visual(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "visual_acceptance_model", "glm-5.3-flash")
    monkeypatch.setattr(settings, "visual_acceptance_apikey", "sk-visual")
    monkeypatch.setattr(settings, "visual_acceptance_base_url", "https://v.example/v1")


async def test_evaluate_sends_image_and_parses_verdict(db_session, monkeypatch) -> None:
    import app.llm.platform_complete as pc

    captured: dict = {}

    async def _fake_pc(prov, apikey, model, system, user_msg, **kw):
        captured.update(
            prov=prov.value,
            apikey=apikey,
            model=model,
            user_msg=user_msg,
            base_url=kw.get("base_url"),
        )
        return json.dumps(_VERDICT), None

    monkeypatch.setattr(pc, "platform_complete", _fake_pc)
    _configure_visual(monkeypatch)

    out = await va.evaluate_visual_acceptance(db_session, b"png-bytes", {"title": "T"}, {})
    assert out is not None and out["match"] is False
    # 消息必须是 content parts：文本 brief + 图片 part（data URI 自包含）
    parts = captured["user_msg"]
    assert isinstance(parts, list) and parts[0]["type"] == "text"
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert captured["model"] == "glm-5.3-flash"
    assert captured["base_url"] == "https://v.example/v1"


async def test_evaluate_degrades_on_failure(db_session, monkeypatch) -> None:
    import app.llm.platform_complete as pc

    async def _boom(*a, **k):
        raise TimeoutError("vision down")

    monkeypatch.setattr(pc, "platform_complete", _boom)
    _configure_visual(monkeypatch)
    assert await va.evaluate_visual_acceptance(db_session, b"png", {}, {}) is None

    async def _empty(*a, **k):
        return "", None  # HTTP 200 但 content 空（thinking 吃光）→ 跳过

    monkeypatch.setattr(pc, "platform_complete", _empty)
    assert await va.evaluate_visual_acceptance(db_session, b"png", {}, {}) is None


# ---------------- execute_playtest 钩子集成 ----------------


async def test_execute_playtest_success_carries_visual_warnings(
    db_session, redis_client, monkeypatch, tmp_path
) -> None:
    from app.forge import code_qa_exec
    from app.hosting import serve

    run_id = uuid.uuid4()
    html = tmp_path / "index.html"
    html.write_text("<html><body>game</body></html>")
    monkeypatch.setattr(code_qa_exec.store, "artifact_dir", lambda *a: tmp_path / "absent")
    monkeypatch.setattr(code_qa_exec.store, "index_path", lambda *a: html)
    monkeypatch.setattr(serve, "is_project_artifact", lambda *a: False)

    from app.sandbox.playtest import make_playtest_result

    fake_pt = make_playtest_result(console_logs=[], thumbnail=b"fake-png", motion_signal="raf")

    async def _fake_run_playtest(*a, **k):
        return fake_pt

    monkeypatch.setattr(code_qa_exec, "run_playtest", _fake_run_playtest)

    seen_events: list[tuple] = []

    async def _fake_publish(rid, ev_type, payload):
        seen_events.append((ev_type, payload))

    monkeypatch.setattr(code_qa_exec, "publish_event", _fake_publish)

    async def _fake_eval(db, png, doc, art):
        assert png == b"fake-png"
        return va.parse_verdict(json.dumps(_VERDICT))

    monkeypatch.setattr(code_qa_exec, "evaluate_visual_acceptance", _fake_eval)

    saved: list = []

    async def _fake_save_thumb(s, game, version, png):
        saved.append((version, png))

    ctx = SimpleNamespace(
        run=SimpleNamespace(id=run_id),
        game=SimpleNamespace(id=uuid.uuid4(), title="T"),
        s=db_session,
    )
    state = {
        "candidate_ready": True,
        "candidate_version": 3,
        "attempt": 1,
        "design_doc": {"title": "T", "engine": {"id": "canvas"}},
        "art_direction": {"palette": ["#111"]},
    }
    result = await code_qa_exec.execute_playtest(
        ctx, state, set_phase=_noop_phase, save_thumbnail=_fake_save_thumb
    )

    # C 级只 warning：qa_ok 不受影响，warning 进结果与 QA_REPORT 事件
    assert result["qa_ok"] is True
    assert result["visual_warnings"] == va.warning_lines(_VERDICT)
    qa_events = [p for t, p in seen_events if t.value == "qa_report"]
    assert qa_events and qa_events[0]["visual_warnings"] == result["visual_warnings"]
    assert saved == [(3, b"fake-png")]


async def _noop_phase(ctx, phase) -> None:
    return None


async def test_execute_playtest_failure_keeps_visual_check_skipped(
    db_session, redis_client, monkeypatch, tmp_path
) -> None:
    """B 级失败（无截图）时不得调用视觉验收——B 级仍是唯一硬门禁。"""
    from app.forge import code_qa_exec
    from app.hosting import serve
    from app.sandbox.playtest import make_playtest_result

    html = tmp_path / "index.html"
    html.write_text("<html><body>game</body></html>")
    monkeypatch.setattr(code_qa_exec.store, "artifact_dir", lambda *a: tmp_path / "absent")
    monkeypatch.setattr(code_qa_exec.store, "index_path", lambda *a: html)
    monkeypatch.setattr(serve, "is_project_artifact", lambda *a: False)

    async def _fail_pt(*a, **k):
        return make_playtest_result(
            errors=["NO_RUNTIME_SIGNAL: no raf/canvas_diff/engine_runtime"],
            failure_kind="product",
        )

    monkeypatch.setattr(code_qa_exec, "run_playtest", _fail_pt)

    async def _must_not_call(*a, **k):
        raise AssertionError("visual acceptance must not run when B-tier fails")

    monkeypatch.setattr(code_qa_exec, "evaluate_visual_acceptance", _must_not_call)

    async def _fake_publish(rid, ev_type, payload):
        pass

    monkeypatch.setattr(code_qa_exec, "publish_event", _fake_publish)

    ctx = SimpleNamespace(
        run=SimpleNamespace(id=uuid.uuid4()),
        game=SimpleNamespace(id=uuid.uuid4(), title="T"),
        s=db_session,
    )
    result = await code_qa_exec.execute_playtest(
        ctx,
        {"candidate_ready": True, "candidate_version": 1, "attempt": 1, "design_doc": {}},
        set_phase=_noop_phase,
        save_thumbnail=_noop_save,
    )
    assert result["qa_ok"] is False
    assert result.get("visual_warnings", []) == []


async def _noop_save(s, game, version, png) -> None:
    return None
