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
    """启动：init langfuse + dev 自动 seed 官方游戏；停机 flush 缓冲 trace（docs/02 §可观测）。"""
    assert_production_secrets(settings)
    init_langfuse()
    if settings.env == "development":
        await _dev_seed_official_games()
    try:
        yield
    finally:
        flush_langfuse()


async def _dev_seed_official_games() -> None:
    """dev 启动自动幂等 seed 官方游戏，避免重建库后忘跑 seed 导致前端 404。

    生产/预发不自动 seed（由部署流程显式跑 scripts/seed_official_games.py）。
    seed 失败仅 log.exception、不阻断启动：dev 起服务调试其他接口不应被 seed 拖死，
    失败时日志提示手动跑 `uv run python -m scripts.seed_official_games`。
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
    version="0.4.0",
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
