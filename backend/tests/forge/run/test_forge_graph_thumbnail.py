"""封面截图副作用：_save_thumbnail 落盘 + 写 thumbnail_path/cover_path，异常静默降级。

_save_thumbnail 是 qa_node 通过分支调用的纯副作用函数（不进 LangGraph state），
单独单测即可覆盖落盘与降级语义，无需驱动整个生成图。
"""

import uuid

import pytest
from sqlalchemy import select

from app.core import db
from app.forge.graph import _save_thumbnail
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.user import User


async def _seed_owner_and_game() -> tuple[uuid.UUID, uuid.UUID, int]:
    """直接建 owner + Game + GameVersion（绕过生成链与 HTTP）。"""
    async with db.SessionLocal() as s:
        owner = User(email=f"cover-{uuid.uuid4()}@b.com", password_hash="x", email_verified=True)
        s.add(owner)
        await s.flush()
        oid = owner.id
        gid = uuid.uuid4()
        s.add(
            Game(
                id=gid,
                owner_id=oid,
                title="封面测试",
                status="draft",
                current_version=1,
                requirement="cover test",
            )
        )
        s.add(
            GameVersion(
                game_id=gid,
                version=1,
                artifact_path=f"{gid}/1/index.html",
                design_doc={},
            )
        )
        await s.commit()
    return oid, gid, 1


async def _load_game(gid: uuid.UUID) -> Game:
    async with db.SessionLocal() as s:
        g = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert g is not None
        return g


async def test_save_thumbnail_writes_file_and_columns() -> None:
    """正常路径：落盘 thumb.png + GameVersion.thumbnail_path + Game.cover_path 均写入。"""
    _oid, gid, version = await _seed_owner_and_game()
    png = b"\x89PNG\r\n\x1a\n fake"

    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        await _save_thumbnail(s, game, version, png)

    # 磁盘产物
    assert await store.read_bytes(gid, version, "thumb.png") == png
    # DB 列
    game = await _load_game(gid)
    assert game.cover_path == "thumb.png"
    async with db.SessionLocal() as s:
        gv = (
            await s.scalars(
                select(GameVersion).where(
                    GameVersion.game_id == gid, GameVersion.version == version
                )
            )
        ).first()
        assert gv is not None and gv.thumbnail_path == "thumb.png"


async def test_save_thumbnail_silent_degrade_on_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """write_bytes 抛异常 → 函数不 raise、不写库，仅 warning 日志（静默降级）。"""
    _oid, gid, version = await _seed_owner_and_game()

    async def _boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(store, "write_bytes", _boom)

    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        # 关键断言：不抛异常（qa_node 调用方不会因封面失败而中断 run）
        await _save_thumbnail(s, game, version, b"\x89PNG")

    # 降级：cover_path 仍为 None，无 thumb.png 产物
    game = await _load_game(gid)
    assert game.cover_path is None
    assert await store.read_bytes(gid, version, "thumb.png") is None
    # 有 warning 诊断日志
    assert any("thumbnail save failed" in r.getMessage() for r in caplog.records), (
        "封面降级应记 warning 日志"
    )
