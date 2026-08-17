#!/usr/bin/env bash
# 本地开发一键启动：docker 中间件 + 后端 API + worker + 前端，单终端聚合日志。
#
# 用法：
#   bash scripts/dev.sh            # 起全部（中间件若未起会自动起）
#   bash scripts/dev.sh --no-docker# 跳过 docker（中间件已在外部跑时用）
#
# Ctrl-C 一次性优雅停止 API/worker/前端；docker 中间件保留（下次复用），可用
# `docker compose down` 单独关。各进程日志带前缀打到当前终端。
#
# 为什么要这样：本地开发无需把 API/worker/前端容器化——它们是同一份代码的不同入口，
# 放容器里改代码要重建镜像，反而慢。docker 只装"有状态的中间件"
# （pg/redis/rabbitmq/embedding）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

START_DOCKER=1
[[ "${1:-}" == "--no-docker" ]] && START_DOCKER=0

BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PIDS=()

log() { printf '\033[36m[dev]\033[0m %s\n' "$*"; }

wait_http() {
  # wait_http <url> <label> <max_attempts> <sleep_s>
  local url="$1" label="$2" max="${3:-60}" sleep_s="${4:-5}"
  local i
  for i in $(seq 1 "$max"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "${label} 已就绪（${url}）"
      return 0
    fi
    log "等待 ${label}… (${i}/${max})"
    sleep "$sleep_s"
  done
  log "\033[33m警告：${label} 未在预期时间内就绪；语义缓存可能空转，Exact Redis 仍可用。\033[0m"
  return 0
}

cleanup() {
  log "正在停止 API/worker/前端（保留 docker 中间件）..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  sleep 2
  for pid in "${PIDS[@]:-}"; do
    kill -9 "$pid" 2>/dev/null || true
  done
  log "已停止。docker 中间件仍在运行，需关闭执行：docker compose down"
}
trap cleanup EXIT INT TERM

if [[ "$START_DOCKER" == "1" ]]; then
  log "检查 Docker 引擎就绪（Docker Desktop 需已启动）..."
  if ! docker info >/dev/null 2>&1; then
    log "\033[31mDocker 引擎未就绪。请先启动 Docker Desktop，待其完全启动后重跑本脚本。\033[0m"
    log "若中间件已用其他方式运行，可加 --no-docker 跳过：bash scripts/dev.sh --no-docker"
    exit 1
  fi
  log "启动 docker 中间件（pg/redis/rabbitmq/embedding，已起则跳过）..."
  # TEI 需要本地模型目录；缺则先用 ModelScope 拉到 data/embedding-models
  if [[ ! -f "$ROOT/data/embedding-models/BAAI/bge-small-zh-v1.5/model.safetensors" ]]; then
    log "首次准备 embedding 模型（BAAI/bge-small-zh-v1.5）…"
    bash "$ROOT/scripts/download_embedding_model.sh"
  fi
  # 多文件构建链：仅当本机还没有 gameforge-builder:v1 时才 build（已有则跳过）
  if ! docker image inspect gameforge-builder:v1 >/dev/null 2>&1; then
    log "未找到 gameforge-builder:v1，开始构建（首次较慢）…"
    docker compose --profile build-sandbox build builder
  else
    log "已存在 gameforge-builder:v1，跳过构建"
  fi
  docker compose up -d postgres redis rabbitmq embedding
  # 首次拉模型可能较慢；语义缓存依赖此服务，API/worker 启动前尽量等就绪
  wait_http "http://127.0.0.1:8080/health" "embedding(TEI)" 60 5
fi

log "启动后端 API (:8000)..."
( cd "$BACKEND" && exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 ) \
  | sed 's/^/[api]    /' &
PIDS+=($!)

log "启动 worker（生成编排）..."
( cd "$BACKEND" && exec uv run python -m app.messaging.worker ) \
  | sed 's/^/[worker] /' &
PIDS+=($!)

log "启动前端 (:5174)..."
( cd "$FRONTEND" && exec pnpm run dev --port 5174) \
  | sed 's/^/[web]    /' &
PIDS+=($!)

log "全部已启动："
log "  前端      http://127.0.0.1:5174"
log "  后端      http://127.0.0.1:8000"
log "  Embedding http://127.0.0.1:8080/v1/embeddings （docker 中间件，Ctrl-C 不关）"
log "  Ctrl-C 停止 API/worker/前端（中间件保留）"
log "-----------------------------------------------------------"

wait
