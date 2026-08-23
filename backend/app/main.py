import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    auth,
    creator,
    dev,
    favorites,
    feedback,
    games,
    health,
    llm_config,
    notifications,
    official,
    preferences,
    profile,
    publish,
    runs,
    templates,
    usage,
)
from app.core import db
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.langfuse import flush_langfuse, init_langfuse
from app.core.logging import setup_logging
from app.core.metrics import register_metrics
from app.core.security_boot import assert_production_secrets
from app.games.official import seed_official_games
from app.hosting import routes as hosting_routes
from app.ws import runs as ws_runs

log = logging.getLogger(__name__)

setup_logging(settings.log_level, service="backend", log_dir=settings.log_dir)

API_V1 = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子：启动时初始化观测与开发数据，停机时刷写 trace。

    作用：校验生产密钥、注册 Langfuse、开发环境自动 seed 官方游戏，退出时 flush trace。
    场景：由 FastAPI lifespan 参数在进程启动/关闭时自动调用。
    参数：_app - FastAPI 应用实例（未使用，仅占位）。
    返回：异步上下文管理器，yield 期间服务处于运行态。
    """
    assert_production_secrets(settings)
    init_langfuse()
    if settings.env == "development":
        await _dev_seed_official_games()
    try:
        yield
    finally:
        flush_langfuse()


async def _dev_seed_official_games() -> None:
    """开发环境启动时幂等写入官方游戏种子数据。

    作用：向数据库插入或刷新内置官方游戏，避免重建库后前端 404。
    场景：lifespan 在 env=development 时调用；生产/预发由部署脚本显式 seed。
    参数：无。
    返回：无；失败仅记录异常日志，不阻断服务启动。
    """
    try:
        async with db.SessionLocal() as session:
            result = await seed_official_games(session)
        log.info(
            "dev seed 完成：created %d、refreshed %d 款官方游戏",
            result.created,
            result.refreshed,
        )
    except Exception:
        log.exception(
            "dev seed 失败（不阻断启动），请手动执行 `uv run python -m scripts.seed_official_games`"
        )


app = FastAPI(
    title="GameForge-Copilot",
    version="1.0.1",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
register_metrics(app)

app.include_router(health.router)
app.include_router(auth.router, prefix=API_V1)
if settings.dev_routes_enabled:
    app.include_router(dev.router, prefix=API_V1)
app.include_router(llm_config.router, prefix=API_V1)
app.include_router(games.router, prefix=API_V1)
app.include_router(official.router, prefix=API_V1)
app.include_router(templates.router, prefix=API_V1)
app.include_router(profile.router, prefix=API_V1)
app.include_router(preferences.router, prefix=API_V1)
app.include_router(creator.router, prefix=API_V1)
app.include_router(favorites.router, prefix=API_V1)
app.include_router(feedback.router, prefix=API_V1)
app.include_router(runs.router, prefix=API_V1)
app.include_router(publish.router, prefix=API_V1)
app.include_router(usage.router, prefix=API_V1)
app.include_router(notifications.router, prefix=API_V1)
app.include_router(admin.router, prefix=API_V1)
app.include_router(hosting_routes.router)
app.include_router(ws_runs.router)
