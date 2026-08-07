# 09 · 部署与运维

## 部署形态

- 单仓库多服务：`backend/`、`frontend/`、`worker/`、`sandbox`（按 run 拉起）、`postgres`、`redis`。
- Docker Compose 本地与预生产；生产用 GitLab CI 构建镜像推送，K8s 或单机 docker compose 部署。
- 生产级：进程级健康检查、重启策略、日志聚合、密钥注入。
- 可观测 trace 走 langfuse Cloud（SaaS，外部服务，不在 compose 内）；SDK 经环境变量配置，LangGraph callback 自动上报。

## Docker 化

| 镜像 | 说明 |
|---|---|
| `gameforge/backend` | FastAPI，uv 安装依赖，非 root 运行 |
| `gameforge/frontend` | Vite 构建产物由 nginx 托管 |
| `gameforge/sandbox` | execute_code 沙箱镜像，后端按 run 拉起、用完销毁，非常驻 |
| `postgres:16` | 主数据 |
| `redis:7` | 用量/会话/限流/检查点（AOF 持久化） |
| `rabbitmq:3-management` | 任务队列 + WS 事件 topic |
| `gameforge/worker` | RabbitMQ consumer（邮件/生成 run） |

- 沙箱镜像最小化、只读根文件系统、seccomp 限制系统调用。
- 后端镜像分层：依赖层与代码层分离，缓存友好。

## 异步任务队列

- 选型 **RabbitMQ**（`aio-pika` + async consumer，契合 FastAPI async 栈）。
- 用途：邮件发送（验证/重置/通知）、Forge `execute_run` / `resume_run`、WS 事件 topic（`gameforge.ws`）。
- **Redis 保留**：用量统计、限流、refresh token、LangGraph 检查点、run pause/cancel 标志——**不能**用 RabbitMQ 替代。
- 不用 FastAPI BackgroundTasks（进程内、重启即丢，非生产级）。
- Worker 独立进程：`uv run python -m app.messaging.worker`；docker compose 起 `gameforge/worker`。
- 本地/CI 测试：`MESSAGING_BACKEND=memory`（进程内 bus，无需 RabbitMQ 容器）。

```env
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
MESSAGING_BACKEND=rabbitmq   # memory | rabbitmq
```

## 环境变量（非硬编码）

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
MESSAGING_BACKEND=rabbitmq
# 加密
LLM_APIKEY_ENCRYPTION_KEY=           # Fernet key
JWT_SECRET=                          # access 签名
# 邮件
SMTP_HOST/PORT/USER/PASS/FROM
# 托管
HOSTING_ROOT=                        # 产物根目录或 S3 配置
S3_ENDPOINT/BUCKET/AK/SK             # 对象存储（可选）
# 沙箱
SANDBOX_IMAGE=gameforge/sandbox
SANDBOX_DEFAULT_TIER=...             # CPU/mem/time 分级
# 限流/配额
DEFAULT_DAILY_TOKEN_LIMIT=...
DEFAULT_RATE_LIMIT_PER_MIN=...
# langfuse（SaaS Cloud，trace/prompt 回放上报）
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
# 全局
ENV=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://...
```

- 全部走环境变量或配置中心，禁硬编码密钥（安全规范）。

## CI（GitLab CI）

| 阶段 | 任务 |
|---|---|
| lint | ruff check / mypy / eslint / prettier |
| test | pytest（后端）/ vitest（前端） |
| build | 构建前后端与沙箱镜像，推送 registry |
| migrate | alembic upgrade head（预生产/生产，手动 gate） |
| deploy | 生产部署（手动审批） |

- 主分支保护，PR 合并触发 CI；禁止直推/force push main。

## 数据库迁移

- Alembic 管理 schema，CI 在预生产自动迁移，生产手动 gate。
- 破坏性迁移走在线变更流程（先兼容旧代码→迁移→切代码）。
- **官方预置游戏（R1）不随 migrate 写入**，新环境在 `alembic upgrade head` 后须执行：

```bash
cd backend && uv run python -m scripts.seed_official_games
```

幂等，可重复执行；Docker 环境：`docker compose exec backend uv run python -m scripts.seed_official_games`。

## 运维与监控

| 项 | 措施 |
|---|---|
| 健康检查 | `/health` + `/ready`（`db` / `redis` / `rabbitmq` 连通；`memory` 后端时 `rabbitmq=true`） |
| 日志 | 结构化 JSON 日志，stdout 聚合 |
| 指标 | Prometheus（请求数/延迟/LLM 调用/token 用量/沙箱执行数）— 进阶 |
| 链路 | generation_run 全链路 trace 上报 langfuse Cloud，可回看（注意：prompt/生成内容出域） |
| 告警 | 系统总量阈值、错误率、沙箱失败率 |
| 备份 | PostgreSQL 每日全量 + WAL 归档；Redis 开 AOF 持久化（检查点/refresh token 需持久化，丢=长任务不可恢复/用户被登出） |

## 沙箱运维

- 沙箱资源分级配额（CPU/内存/时间），按 run 销毁。
- 沙箱失败/超时：run 挂起交人，事件可观测。
- 沙箱镜像定期更新工具链，扫描漏洞。

## 上线检查清单

- [ ] 密钥全走环境变量，无硬编码
- [ ] CORS/限流/鉴权中间件就位
- [ ] 邮件可达（验证/重置/通知）
- [ ] DB 迁移已执行
- [ ] 官方预置游戏 seed 已执行（`scripts.seed_official_games`；`/api/v1/official-games` 返回 3 项）
- [ ] Redis key 命名空间无冲突
- [ ] 沙箱无网络、资源分级生效
- [ ] 日志聚合与告警就位
- [ ] 备份策略生效
- [ ] langfuse Cloud key 已配，trace 上报正常
- [ ] 已确认 prompt/生成内容出域到 langfuse Cloud（合规确认）
