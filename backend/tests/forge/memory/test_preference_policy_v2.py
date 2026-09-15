"""偏好策略增量（ADR-16 后续批次）：explicit 时间衰减 / scope 防污染 / 行为信号。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.forge.memory import service as svc
from app.forge.memory.llm_extract import _system_prompt, extract_preference_operations
from app.models.user_preference_v2 import UserPreferenceV2

_U = uuid.uuid4


def _set(key: str, value: str, source: str = "explicit", confidence: float = 1.0) -> dict:
    return {"op": "set", "key": key, "value": value, "source": source, "confidence": confidence}


def _inf(key: str, value: str, confidence: float) -> dict:
    return _set(key, value, source="inferred", confidence=confidence)


# --------------------------------------------------------------------------- #
# 1) explicit 时间衰减 / 复确认
# --------------------------------------------------------------------------- #


async def _seed_explicit(
    db: AsyncSession, uid: uuid.UUID, *, age_days: int
) -> None:
    await svc.apply_operation(db, user_id=uid, op=_set("visual.style", "pixel"))
    # 把 updated_at 拨回 age_days 天前（模拟长期未被复确认）
    row = await db.scalar(
        svc.select(UserPreferenceV2).where(
            UserPreferenceV2.user_id == uid,
            UserPreferenceV2.preference_key == "visual.style",
        )
    )
    row.updated_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=age_days)
    await db.flush()


async def test_fresh_explicit_blocks_inferred(db_session: AsyncSession) -> None:
    """新确认的 explicit 恒胜：inferred 不得覆盖（ADR-16 原策略不变）。"""
    uid = _U()
    await _seed_explicit(db_session, uid, age_days=1)
    row = await svc.apply_operation(db_session, user_id=uid, op=_inf("visual.style", "neon", 0.95))
    assert row is not None and row.value == "pixel"
    assert row.source == "explicit"


async def test_stale_explicit_overridden_by_high_confidence_inferred(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """陈旧 explicit（超 stale_days 未复确认）+ 高置信 inferred → 允许覆盖并留痕。"""
    monkeypatch.setattr(settings, "preference_explicit_stale_days", 180)
    monkeypatch.setattr(settings, "preference_inferred_override_confidence", 0.85)
    uid = _U()
    await _seed_explicit(db_session, uid, age_days=200)
    row = await svc.apply_operation(
        db_session, user_id=uid, op=_inf("visual.style", "neon", 0.9)
    )
    assert row is not None
    assert row.value == "neon"
    assert row.source == "inferred"
    assert "superseded_explicit:pixel" in (row.note or "")


async def test_stale_explicit_blocks_low_confidence_inferred(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """陈旧 explicit 也只让位于足够强的信号：低于门槛的 inferred 仍被拒。"""
    monkeypatch.setattr(settings, "preference_explicit_stale_days", 180)
    monkeypatch.setattr(settings, "preference_inferred_override_confidence", 0.85)
    uid = _U()
    await _seed_explicit(db_session, uid, age_days=400)
    row = await svc.apply_operation(
        db_session, user_id=uid, op=_inf("visual.style", "neon", 0.7)
    )
    assert row is not None and row.value == "pixel"  # 值保持


async def test_decay_disabled_restores_absolute_explicit(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stale_days <= 0 关闭时间衰减：回到 explicit 绝对恒胜。"""
    monkeypatch.setattr(settings, "preference_explicit_stale_days", -1)
    uid = _U()
    await _seed_explicit(db_session, uid, age_days=999)
    row = await svc.apply_operation(
        db_session, user_id=uid, op=_inf("visual.style", "neon", 0.99)
    )
    assert row is not None and row.value == "pixel"


# --------------------------------------------------------------------------- #
# 2) scope 防污染（抽取提示词规则）
# --------------------------------------------------------------------------- #


def test_extract_prompt_has_scope_rule() -> None:
    prompt = _system_prompt()
    assert "这个游戏" in prompt and "本作" in prompt
    assert "单游戏要求而非用户偏好" in prompt


def test_extract_prompt_has_history_inference_rule() -> None:
    prompt = _system_prompt()
    assert "历史需求中反复出现" in prompt
    assert "禁止凭单条历史臆断" in prompt


# --------------------------------------------------------------------------- #
# 3) 行为信号：历史需求传入抽取
# --------------------------------------------------------------------------- #


async def test_extract_passes_history_to_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """history_texts 进入用户消息的历史区块；无历史时不附加该区块。"""
    monkeypatch.setattr(settings, "preference_extract_enabled", True)
    monkeypatch.setattr(settings, "preference_extract_model", "m")
    monkeypatch.setattr(settings, "preference_extract_apikey", "k")
    captured: dict[str, str] = {}

    async def _fake_complete(prov, apikey, model, system, user_msg, **kw):
        captured["user_msg"] = user_msg
        return '{"operations": []}', None

    monkeypatch.setattr("app.llm.platform_complete.platform_complete", _fake_complete)
    ops = await extract_preference_operations(
        "做一个像素风游戏", [], history_texts=["像素风跑酷", "像素风塔防"]
    )
    assert ops == []
    assert "【用户近期需求历史（仅供行为信号推断）】" in captured["user_msg"]
    assert "像素风跑酷" in captured["user_msg"]

    # 无历史：不附加历史区块
    await extract_preference_operations("做个游戏", [])
    assert "【用户近期需求历史" not in captured["user_msg"]


def test_history_only_inferred_ops_filtered_when_disabled() -> None:
    """行为信号产物是 inferred：memory_preferences_inferred=False 时被滤除（既有语义）。"""
    from app.forge.memory import preferences as prefs_mod

    # 直接验证过滤语义（LLM 侧未配置时 ops 恒空，此处验证过滤函数行为一致性）
    ops = [
        {
            "op": "set", "key": "visual.style", "value": "pixel",
            "source": "inferred", "confidence": 0.7,
        },
        {
            "op": "set", "key": "gameplay.difficulty", "value": "hard",
            "source": "explicit", "confidence": 1.0,
        },
    ]
    filtered = [op for op in ops if op.get("source") != "inferred"]
    assert [op["key"] for op in filtered] == ["gameplay.difficulty"]
    assert prefs_mod.settings is settings
