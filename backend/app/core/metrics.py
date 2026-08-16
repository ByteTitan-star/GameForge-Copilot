"""Prometheus 指标（docs/09 §运维与监控）。

请求数/延迟、LLM 调用、token 用量、沙箱执行数。
"""

import time
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

REQUESTS = Counter(
    "gameforge_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "gameforge_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
LLM_CALLS = Counter(
    "gameforge_llm_calls_total",
    "LLM completions",
    ["provider", "status"],
)
LLM_TOKENS = Counter(
    "gameforge_llm_tokens_total",
    "LLM tokens consumed",
    ["provider", "direction"],
)
SANDBOX_RUNS = Counter(
    "gameforge_sandbox_executions_total",
    "Sandbox executions",
    ["backend", "status"],
)
SANDBOX_TIER_RUNS = Counter(
    "gameforge_sandbox_tier_executions_total",
    "Sandbox executions by resource tier",
    ["backend", "tier", "status"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)
        path = request.url.path
        # 收敛高基数路径：UUID 段替换
        label_path = _normalize_path(path)
        start = time.perf_counter()
        response = await call_next(request)
        LATENCY.labels(request.method, label_path).observe(time.perf_counter() - start)
        REQUESTS.labels(request.method, label_path, str(response.status_code)).inc()
        return response


def _normalize_path(path: str) -> str:
    parts = []
    for p in path.split("/"):
        if not p:
            continue
        if len(p) >= 32 and all(c in "0123456789abcdef-" for c in p.lower()):
            parts.append("{id}")
        elif p.isdigit():
            parts.append("{n}")
        else:
            parts.append(p)
    return "/" + "/".join(parts) if parts else "/"


def register_metrics(app: FastAPI) -> None:
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
