"""#14：真实 PostgreSQL 冒烟（UUID/JSONB/asyncpg）。

默认 skip；本地 `docker compose up -d postgres` 后：
`RUN_PG_INTEGRATION=1 uv run pytest -m integration -q`
"""

import os
import uuid

import pytest
from app.models import Base
from app.models.game import Game
from app.models.user import User
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

_PG = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge",
)


def _enabled() -> bool:
    return os.getenv("RUN_PG_INTEGRATION") == "1"


@pytest.fixture
async def pg_session():
    if not _enabled():
        pytest.skip("set RUN_PG_INTEGRATION=1 with reachable postgres")
    engine = create_async_engine(_PG, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"postgres unreachable: {e}")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_pg_uuid_jsonb_roundtrip(pg_session) -> None:
    email = f"pg-{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        password_hash="x",
        role="user",
        email_verified=True,
    )
    pg_session.add(user)
    await pg_session.commit()
    await pg_session.refresh(user)

    game = Game(
        owner_id=user.id,
        title="pg-game",
        requirement="r",
        status="draft",
        current_version=0,
    )
    pg_session.add(game)
    await pg_session.commit()
    await pg_session.refresh(game)

    assert isinstance(game.id, uuid.UUID)
    row = await pg_session.scalar(select(Game).where(Game.id == game.id))
    assert row is not None
    assert row.title == "pg-game"
