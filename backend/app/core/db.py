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
    """请求级数据库会话依赖注入。

    作用：为每个 HTTP 请求创建并 yield 一个 AsyncSession，请求结束后自动关闭。
    场景：FastAPI 路由通过 Depends(get_db) 获取数据库会话。
    参数：无。
    返回：异步生成器，产出 AsyncSession 实例。
    """
    async with SessionLocal() as session:
        yield session
