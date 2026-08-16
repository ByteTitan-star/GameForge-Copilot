"""ADR-04：forge_messages 为会话唯一 SoT；禁止并行会话表模型。"""

from __future__ import annotations

from pathlib import Path

import app.models as models_pkg

_FORBIDDEN_TABLE_FRAGMENTS = (
    "conversation",
    "chat_message",
    "session_message",
    "vector_message",
    "message_embedding",
)


def test_forge_messages_is_sole_conversation_sot_among_orm_models() -> None:
    tables = {
        cls.__tablename__
        for name in dir(models_pkg)
        if not name.startswith("_")
        for cls in [getattr(models_pkg, name)]
        if hasattr(cls, "__tablename__")
    }
    assert "forge_messages" in tables
    offenders = [
        t
        for t in tables
        if t != "forge_messages"
        and any(frag in t for frag in _FORBIDDEN_TABLE_FRAGMENTS)
    ]
    assert offenders == [], f"unexpected parallel conversation tables: {offenders}"


def test_no_vector_conversation_store_module_in_forge() -> None:
    forge_root = Path(__file__).resolve().parents[1] / "app" / "forge"
    banned = ("vector_store", "conversation_vector", "msg_embedding")
    hits: list[str] = []
    for path in forge_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                hits.append(f"{path.name}:{token}")
    assert hits == []
