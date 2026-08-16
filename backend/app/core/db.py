from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_connect_args: dict[str, object] = {}
if settings.database_url.startswith("postgresql"):
    _connect_args = {
        "timeout": settings.db_connect_timeout,
        "command_timeout": settings.db_command_timeout,
    }

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """请求级 DB 会话依赖；失败由调用方显式处理，不静默吞。"""
    async with SessionLocal() as session:
        yield session
