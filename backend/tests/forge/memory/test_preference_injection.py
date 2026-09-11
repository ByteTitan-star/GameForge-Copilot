"""偏好注入（ADR-16）：按节点解析 + source/confidence 渲染进 MEMORY_DATA。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.forge.memory import service as svc
from app.forge.memory.context_builder import _format_preferences
from app.forge.memory.loader import build_node_context
from app.models.game import Game
from app.models.user import User


def _op(key: str, value: str, source: str = "explicit", confidence: float = 1.0) -> dict:
    return {"op": "set", "key": key, "value": value, "source": source, "confidence": confidence}


def test_format_preferences_renders_source_and_confidence() -> None:
    prefs: list[dict[str, Any]] = [
        {"key": "visual.style", "value": "pixel", "source": "explicit", "confidence": 1.0},
        {"key": "gameplay.difficulty", "value": "hard", "source": "inferred", "confidence": 0.65},
    ]
    text = _format_preferences(prefs)
    assert "- visual.style=pixel (explicit, 1.0)" in text
    assert "- gameplay.difficulty=hard (inferred, 0.65)" in text


async def _make_user_game(db: AsyncSession) -> tuple[uuid.UUID, Game]:
    user = User(
        id=uuid.uuid4(),
        email=f"inject-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db.add(user)
    await db.flush()
    game = Game(
        id=uuid.uuid4(),
        owner_id=user.id,
        title="注入测试",
        requirement="测试",
    )
    db.add(game)
    await db.flush()
    return user.id, game


async def test_build_node_context_scopes_preferences_by_node(db_session: AsyncSession) -> None:
    uid, game = await _make_user_game(db_session)
    await svc.apply_operation(
        db_session, user_id=uid, op=_op("gameplay.difficulty", "hard", "inferred", 0.65)
    )
    await svc.apply_operation(db_session, user_id=uid, op=_op("visual.palette", "dark"))
    await db_session.commit()

    built = await build_node_context(
        db_session, node="art", game=game, user_id=uid, current_input="画一个开始界面"
    )
    # MEMORY_DATA 内嵌于 user_message；断言节点域与渲染形态
    assert "visual.palette=dark (explicit, 1.0)" in built.user_message
    assert "gameplay.difficulty" not in built.user_message  # plan 专属偏好不进 art
