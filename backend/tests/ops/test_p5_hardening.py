"""P5 hardening：diagnose Memory 信封、Art/QA skill 接线、安全扫描与 cache chaos。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import fakeredis.aioredis
import pytest

from app.forge.cache.exact import exact_cache_get, exact_cache_set, is_cacheable_node
from app.forge.prompts import (
    build_art_detail_prompt,
    build_art_options_prompt,
    build_qa_prompt,
)
from app.forge.qa.diagnose import diagnose_playtest_failure, fallback_diagnosis


def test_build_art_options_prompt_injects_methodology(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_art_options_prompt({"style": "像素风 HUD"})
    assert "【Skill:" in prompt or "pixel" in prompt.lower() or "HUD" in prompt
    assert prompt.count("【Skill:") <= 3


def test_build_art_detail_prompt_includes_policy_or_methodology(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_art_detail_prompt({"goal": "平台跳跃"})
    assert "合法 JSON" in prompt
    assert "【Policy:" in prompt or "【Skill:" in prompt


def test_build_qa_prompt_includes_repair_skills(monkeypatch) -> None:
    monkeypatch.setattr("app.forge.prompts.settings.skills_router_enabled", True)
    prompt = build_qa_prompt(failure_kind="product")
    assert "JSON" in prompt
    assert "runtime" in prompt.lower() or "回归" in prompt or "【Skill:" in prompt


@pytest.mark.asyncio
async def test_diagnose_uses_memory_prefix_without_duplicating_design() -> None:
    captured: dict[str, str] = {}

    async def fake_llm(system: str, user_msg: str) -> str:
        captured["system"] = system
        captured["user"] = user_msg
        return fallback_diagnosis(["boom"])

    out = await diagnose_playtest_failure(
        llm=fake_llm,
        design_doc={"title": "should-not-appear-twice"},
        errors=["pageerror"],
        console_logs=["err"],
        source_excerpt="<html></html>",
        memory_prefix="【MEMORY_DATA】\nprefix-only",
        failure_kind="product",
    )
    assert "prefix-only" in captured["user"]
    assert "pageerror" in captured["user"]
    assert "should-not-appear-twice" not in captured["user"]
    assert "root_causes" in out


@pytest.mark.asyncio
async def test_exact_cache_chaos_forbidden_never_writes_under_concurrency() -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def attempt(i: int) -> None:
        node = "code" if i % 2 == 0 else "plan"
        assert not is_cacheable_node(node)
        ok = await exact_cache_set(r, node=node, input_payload={"i": i}, value={"x": i})
        assert ok is False
        assert await exact_cache_get(r, node=node, input_payload={"i": i}) is None

    await asyncio.gather(*(attempt(i) for i in range(40)))
    assert await r.keys("forge:exact:*") == []


def test_secret_scan_script_flags_private_key(tmp_path: Path, monkeypatch) -> None:
    import importlib.util

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "secret_scan", root / "scripts" / "secret_scan.py"
    )
    assert spec is not None and spec.loader is not None
    secret_scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secret_scan)

    bad = tmp_path / "leak.txt"
    bad.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(secret_scan, "_staged_files", lambda: [bad])
    assert secret_scan.main(["--staged"]) == 1
    findings = secret_scan._scan_text(bad, bad.read_text(encoding="utf-8"))
    assert findings and "private_key" in findings[0]
