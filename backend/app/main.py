from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, games, health, llm_config, notifications, publish, runs, usage
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.metrics import register_metrics
from app.hosting import routes as hosting_routes
from app.ws import runs as ws_runs

setup_logging(settings.log_level)

API_V1 = "/api/v1"

app = FastAPI(
    title="GameForge-Copilot",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url=None,
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
app.include_router(llm_config.router, prefix=API_V1)
app.include_router(games.router, prefix=API_V1)
app.include_router(runs.router, prefix=API_V1)
app.include_router(publish.router, prefix=API_V1)
app.include_router(usage.router, prefix=API_V1)
app.include_router(notifications.router, prefix=API_V1)
app.include_router(admin.router, prefix=API_V1)
app.include_router(hosting_routes.router)
app.include_router(ws_runs.router)
