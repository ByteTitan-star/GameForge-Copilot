# 本地开发

[中文产品 README](../README_zh.md) · [English README](../README.md)

本说明收录从产品介绍首页移出的详细启动、配置、验证和排错信息。

## 前置条件

首次启动前请安装：

- Docker Desktop（包含 Docker Compose）
- Node.js 20+ 和 pnpm 9+
- [uv](https://docs.astral.sh/uv/)

`uv` 会在需要时根据 `backend/.python-version` 解析后端需要的 Python 3.12 运行时。

## 本地配置

从示例文件创建不会提交到 Git 的本地配置：

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

默认值适用于本地 Docker 依赖。不要提交 `.env`，也不要在文档、截图或录屏中写入 API Key。

### 关键变量

| 文件 | 变量 | 本地默认值 | 用途 |
| --- | --- | --- | --- |
| `backend/.env` | `DATABASE_URL` | `postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge` | PostgreSQL 连接 |
| `backend/.env` | `REDIS_URL` | `redis://localhost:6379/0` | 缓存和生成检查点 |
| `backend/.env` | `RABBITMQ_URL` | `amqp://gameforge:gameforge@localhost:5672/` | Worker 队列和实时事件 |
| `backend/.env` | `CORS_ORIGINS` | `http://127.0.0.1:5173,...` | API 允许的浏览器来源 |
| `backend/.env` | `SANDBOX_BACKEND` | `local` | 本地开发使用的构建后端；仅在构建 Sandbox Image 后使用 `docker` |
| `backend/.env` | `THUMBNAIL_ENABLED` | `true` | Playwright QA 通过后可选截取游戏卡片封面 |
| `backend/.env` | `CODE_QA_MAX_ATTEMPTS` | `3` | CodeQaLoop 总 attempt（含首次 generate） |
| `frontend/.env` | `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | REST API 基础地址 |
| `frontend/.env` | `VITE_HOSTING_BASE_URL` | 可选 | `/play` 和 `/draft` 页的托管根地址 |
| `frontend/.env` | `VITE_WS_BASE_URL` | 可选 | WebSocket 根地址；留空时自动推导 |

完整字段请阅读带注释的 `backend/.env.example` 和 `frontend/.env.example`。

## 首次启动

在仓库根目录启动三个必要的基础服务：

```bash
docker compose up -d postgres redis rabbitmq
docker compose ps
```

然后初始化后端依赖、数据库结构和内置官方游戏：

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_official_games
```

修改官方游戏源资产后可再次运行 seed 命令；它可以重复执行。

## 启动应用

API、Worker 和前端是三个独立的本地进程。请分别在三个终端中启动：

```bash
# API
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Worker
cd backend
uv run python -m app.messaging.worker
```

```bash
# 前端
cd frontend
pnpm install
pnpm run dev
```

浏览器打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。后端 API 文档地址为 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

邮箱验证和游戏生成依赖 Worker。使用默认开发邮件配置时，验证码会输出到 Worker 终端，而不是通过 SMTP 发送。

## 健康检查

服务启动后可以用以下入口验证：

| 检查项 | 地址 | 预期结果 |
| --- | --- | --- |
| API 存活 | [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz) | API 正常响应 |
| 依赖就绪 | [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready) | PostgreSQL、Redis 和 RabbitMQ 均已就绪 |
| API 契约 | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | 可交互的 OpenAPI 文档 |
| 官方试玩游戏 | [http://127.0.0.1:8000/play/official-neon-snake](http://127.0.0.1:8000/play/official-neon-snake) | 可试玩的 HTML 页面 |

## 测试与构建

在各自应用目录运行测试：

```bash
# 后端测试
cd backend
uv run pytest -q
```

```bash
# 前端单元测试
cd frontend
pnpm test

# 类型检查和生产构建
pnpm run build
```

可选的真实服务冒烟检查要求 API 和本地依赖已经运行：

```bash
cd frontend
pnpm smoke:real
```

## Docker 后端模式

如需将 API 和 Worker 也放入 Docker，先构建 Sandbox Image，再启动服务：

```bash
docker compose --profile build-sandbox build sandbox
docker compose up -d postgres redis rabbitmq backend worker
```

在新环境中，需要在 backend 容器中执行迁移和官方游戏初始化：

```bash
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m scripts.seed_official_games
```

开发期间前端通常仍在本地通过 `pnpm run dev` 运行。

## 必需的浏览器试玩（CodeQaLoop）

执行生成任务的 Worker **必须**具备 Playwright + Chromium。静态 DOM 检查仅作诊断，不得作为 QA 通过依据。缺少浏览器时 CodeQaLoop 记 `failure_kind=infra`，无法进入 `done`。

在 Worker 机器上安装：

```bash
cd backend
uv sync --extra playwright
uv run playwright install chromium
```

Windows PowerShell：

```powershell
cd backend
uv sync --extra playwright
uv run playwright install chromium
uv run python -m app.messaging.worker
```

Linux 容器应将浏览器依赖写入 Worker 镜像（见 `docker/Dockerfile.worker` 的 `playwright install --with-deps`）。截图失败只影响封面（`THUMBNAIL_ENABLED`）；缺少 Chromium 会阻断 QA 通过。

## Windows 排错

| 现象 | 检查与处理 |
| --- | --- |
| 找不到 `uv` 或 `pnpm` | 安装对应工具，重新打开终端后再运行命令。 |
| 前端无法使用 5173 启动 | 关闭占用 5173 的进程，或有意修改 Vite 端口，并同步更新 `CORS_ORIGINS` 与 `FRONTEND_BASE_URL`。 |
| 浏览器请求失败或登录注册无响应 | 全程统一使用 `127.0.0.1` 或 `localhost`。默认配置使用 `127.0.0.1`。修改 CORS 后需要重启 API。 |
| `/ready` 报依赖不可用 | 打开 Docker Desktop，运行 `docker compose ps`，确认 PostgreSQL、Redis 和 RabbitMQ 均为 healthy。 |
| 没有验证码或 Forge 一直排队 | 确认 Worker 终端正在运行并且已连接 RabbitMQ。 |
| Forge 尚未开始就失败 | 检查邮箱是否完成验证，并在设置页保存和测试可用的 LLM Provider 配置。 |
| 游戏卡片没有截图封面 | 需 Worker 已装 Playwright + Chromium 且 `THUMBNAIL_ENABLED=true`。缺少 Chromium 同时会阻断 CodeQaLoop 通过。 |
| 本地数据库结构过旧 | 在 `backend/` 中运行 `uv run alembic upgrade head`。 |

## 端口

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://127.0.0.1:5173` |
| API | `http://127.0.0.1:8000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| RabbitMQ AMQP | `localhost:5672` |
| RabbitMQ 管理台 | `http://127.0.0.1:15672` |

## 相关项目文档

- [OpenAPI 契约](../contracts/openapi.json)
- [API 联调说明](../contracts/INTEGRATION.md)
- [API 变更记录](../contracts/CHANGELOG.md)
