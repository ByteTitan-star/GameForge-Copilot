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
FAILURE_CLASS_TOTAL = Counter(
    "forge_failure_class_total",
    "FailureReport classifications",
    ["failure_class", "source"],
)
FAILURE_CLASS_UNKNOWN = Counter(
    "forge_failure_class_unknown_total",
    "FailureReports classified as unknown",
)
FAILURE_CLASS_OVERRIDE = Counter(
    "forge_failure_class_override_total",
    "LLM diagnosis ignored because a hard rule already classified the failure",
)
FAILURE_RECOVERY_MISMATCH = Counter(
    "forge_failure_recovery_mismatch_total",
    "suggested_recovery not in HITL allowed_commands",
)
ART_REUSE = Counter(
    "forge_art_reuse_total",
    "Art revisions reused after replan because dependency fingerprint matched",
)
ART_REGENERATE = Counter(
    "forge_art_regenerate_total",
    "Art revisions regenerated because dependency fingerprint changed or version differed",
)
NATIVE_ENGINE_PHASE_TOTAL = Counter(
    "gameforge_native_engine_phase_total",
    "Native engine validate/build/run phase outcomes",
    ["engine", "phase", "status"],
)
NATIVE_ENGINE_PHASE_LATENCY = Histogram(
    "gameforge_native_engine_phase_duration_seconds",
    "Native engine phase duration",
    ["engine", "phase"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)
NATIVE_ENGINE_ERRORS = Counter(
    "gameforge_native_engine_error_total",
    "Native engine failures by error taxonomy",
    ["engine", "phase", "error_type"],
)
NATIVE_ENGINE_LOOP_TOTAL = Counter(
    "gameforge_native_engine_loop_total",
    "Native engine full P0 loop outcomes",
    ["engine", "status"],
)
NATIVE_ENGINE_LOOP_LATENCY = Histogram(
    "gameforge_native_engine_loop_duration_seconds",
    "Native engine full P0 loop duration",
    ["engine"],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
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
