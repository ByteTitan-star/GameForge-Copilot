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


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """采集 HTTP 请求延迟与状态码指标。

        作用：对非 /metrics 请求计时并递增 Prometheus 计数器。
        场景：作为 Starlette 中间件挂载后，每个入站请求自动执行。
        参数：request - 当前 HTTP 请求；call_next - 下游处理链。
        返回：下游响应对象。
        """
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
    """将 URL 路径中的动态段替换为占位符以降低指标基数。

    作用：把 UUID 段替换为 {id}、纯数字段替换为 {n}。
    场景：Prometheus 打点前规范化 request.url.path。
    参数：path - 原始 URL 路径。
    返回：用于指标标签的规范化路径字符串。
    """
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
    """注册 Prometheus 中间件与 /metrics 抓取端点。

    作用：挂载请求指标采集中间件并暴露 metrics 路由。
    场景：FastAPI 应用启动装配时调用一次。
    参数：app - FastAPI 应用实例。
    返回：无。
    """
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """返回 Prometheus 文本格式的指标快照。

        作用：序列化当前进程内已注册的 Counter/Histogram。
        场景：运维或 Prometheus 抓取 GET /metrics 时调用。
        参数：无。
        返回：content-type 为 Prometheus 标准的 HTTP 响应。
        """
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
