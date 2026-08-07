# GameForge-Copilot

🎮 浏览器里做小游戏：用平常话讲规则，生成后马上在网页里玩，改到满意再公开。

> 说完就能玩 · 前端直连真实后端 API（见下方「本地开发」）。

<p align="center">
  <img src="docs/assets/01-landing.png" alt="GameForge Landing" width="900" />
</p>

<p align="center">
  <code>描述玩法</code> → <code>确认策划</code> → <code>生成构建</code> → <code>浏览器试玩</code> → <code>提交发布</code>
</p>

<p align="center">
  <a href="#从零启动">从零启动</a> ·
  <a href="#demo-cases">Cases</a> ·
  <a href="#product-ui">UI</a> ·
  <a href="#for-contributors">Contributors</a>
</p>

---

## 从零启动

仓库根目录即本文件所在目录（下文命令均相对仓库根，即 `autoGame/`）。

### 0. 准备环境

| 工具 | 用途 | 版本建议 |
|---|---|---|
| [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/) | 前端 | Node 20+，pnpm 9+ |
| [uv](https://docs.astral.sh/uv/) | 后端 Python 依赖与运行 | 最新稳定版 |
| Python | 由 uv 按 `.python-version` 拉取 | **3.12** |
| [Docker](https://docs.docker.com/get-docker/) + Compose | Postgres / Redis / RabbitMQ（以及可选整栈） | 有 Docker 时推荐 |

本机没有 Docker 时：需自行安装 Postgres/Redis 并改 `backend/.env`，或使用 Podman 等价 compose。

---

### 本地开发（前端 + 真实后端）

需要 **5 个终端**（或等价后台进程）：Postgres + Redis + RabbitMQ → API → Worker → 前端。

> Worker 消费 **RabbitMQ**（任务 + WS 事件 topic）；**Redis 仍保留** KV（用量 / 限流 / token / 检查点）。前端只连 HTTP / WS。

#### 1. 拉起数据库、Redis 与 RabbitMQ

在仓库根目录：

```bash
docker compose up -d postgres redis rabbitmq
```

默认账号（与 `backend/.env.example` 一致）：

- Postgres：`postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge`
- Redis：`redis://localhost:6379/0`
- RabbitMQ：`amqp://gameforge:gameforge@localhost:5672/`（管理台 http://127.0.0.1:15672）

#### B2. 安装并启动后端 API

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

自检：

- 存活：[http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)
- 就绪（DB + Redis + RabbitMQ）：[http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready) → `db` / `redis` / `rabbitmq` 均为 `true`
- OpenAPI 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

说明：

- `LLM_APIKEY_ENCRYPTION_KEY` 可留空（开发环境会从 `JWT_SECRET` 派生）；生产必须单独配置。
- `SMTP_*` 留空时，验证/重置邮件会打到 **Worker 终端**（`[dev-email] ...`），不会真发信。
- 本地沙箱默认 `SANDBOX_BACKEND=local`（子进程），不强制 Docker 沙箱镜像。

#### B3. 启动 Worker（RabbitMQ 消费者：邮件 + 生成任务）

另开一个终端，仍在 `backend/`：

```bash
cd backend
uv run python -m app.messaging.worker
```

没有 Worker：注册后收不到验证链接打印，发起生成 run 也不会真正执行。

#### 4. 启动前端

```bash
cd frontend
cp .env.example .env   # 默认 VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
pnpm install           # 若尚未安装
pnpm dev
```

打开：[http://127.0.0.1:5173](http://127.0.0.1:5173)

联调自检（API 已起时）：

```bash
pnpm smoke:real
```

#### 5. 第一次用真实后端时怎么走

1. 打开注册页，注册自己的邮箱与密码。
2. 到 **Worker 终端** 找到 `[dev-email]` 里的验证链接，点开完成邮箱验证。
3. 登录 → 设置页配置 LLM（provider / model / apikey；`openai_compat` 需填 `base_url`）。
4. 进入工坊，用一句话说规则，发起生成；中间会停在「确认策划」，批准后继续，右侧可试玩。

管理员账号：需在库里把对应用户 `role` 设为 `admin`（测试里有提权写法；生产勿用手写 SQL 乱改）。

---

### 路径 C — 整栈 Docker Compose（可选）

在仓库根目录一次性起 Postgres、Redis、API、Worker（前端仍建议本机 `pnpm dev` 热更新）：

```bash
# 首次可先构建沙箱镜像（仅当 SANDBOX_BACKEND=docker 时需要）
# docker compose --profile build-sandbox build sandbox

docker compose up -d postgres redis rabbitmq backend worker
```

API 默认映射：[http://127.0.0.1:8000](http://127.0.0.1:8000)

注意：compose 里 backend 使用 `backend/.env.example` 作为 `env_file`，并覆盖 `DATABASE_URL` / `REDIS_URL` 指向容器网络。本机改配置时优先改 `backend/.env`（路径 B）或 compose 的 `environment`。

容器内迁移：若镜像未自动 migrate，进入 backend 容器执行：

```bash
uv run alembic upgrade head
```

---

### 端口与目录速查

| 服务 | 地址 / 路径 |
|---|---|
| 前端 Vite | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000 |
| API 前缀 | `/api/v1` |
| Postgres | `localhost:5432` |
| Redis | `localhost:6379`（用量 / 限流 / token / 检查点） |
| RabbitMQ | `localhost:5672`（任务队列 + WS 事件 topic） |
| RabbitMQ 管理台 | http://127.0.0.1:15672（gameforge / gameforge） |
| 本地产物目录 | `backend/.hosting/`（`HOSTING_ROOT`） |

---

### 常见问题

| 现象 | 处理 |
|---|---|
| 前端跨域 / 登录失败 | 确认后端 `CORS_ORIGINS` 含 `http://127.0.0.1:5173`；前端用该地址打开，不要混用 `localhost` 与 `127.0.0.1` 的 cookie 预期不一致。 |
| `/ready` 里 db/redis/rabbitmq 为 false | `docker compose up -d postgres redis rabbitmq`，或检查 `.env` 连接串与端口占用。 |
| 注册后没有验证邮件 | 确认 Worker 在跑；看 Worker 终端 `[dev-email]` 输出。 |
| 发起生成一直不动 | 确认 Worker 在跑；设置里已配可用 LLM；邮箱已验证。 |
| 前端仍走假数据 | `VITE_USE_MOCK` 必须为 `false`，改完后重启 `pnpm dev`。 |
| `alembic` / `uv` 找不到 | 在 `backend/` 下用 `uv run ...`，先 `uv sync`。 |
| 本机无 Docker | 路径 A 仍可用；路径 B 需自备 Postgres 16 + Redis 7 + RabbitMQ 3。 |

---

## Demo Cases

落地页里的三条样例路径（mock 库同款）。完整卡片见下图。

<p align="center">
  <img src="docs/assets/01-landing-cases.png" alt="Landing features and cases" width="900" />
</p>

| Case | 一句话开局 | 状态 | 你会看到 |
|---|---|---|---|
| **霓虹贪吃蛇** | 「方向键 + 计分，失败一键重开」 | Draft | 进工坊继续打磨、预览、提交发布 |
| **像素跑酷** | 「障碍节奏 + 皮肤切换」 | Published | 公开链接试玩入口 |
| **塔防雏形** | 「路径与波次先数值确认」 | Rejected → 可再提审 | 改策划稿后再出可运行版 |

---

## Product UI

截图来自本地 `pnpm dev` + `VITE_USE_MOCK=true`（2026-08）。顶部绿色条是 mock 提示，不是生产文案。

### 登录 · 液态玻璃

<p align="center">
  <img src="docs/assets/02-login.png" alt="Login" width="900" />
</p>

### 我的游戏 · 深色 Library

封面卡、状态筛选、发布 / 删除。

<p align="center">
  <img src="docs/assets/03-games.png" alt="Games library" width="900" />
</p>

### 设计工坊 · 命令台三栏

左 Chat · 中 Pipeline + 人工确认 · 右事件日志 / 试玩。

<p align="center">
  <img src="docs/assets/04-forge.png" alt="Forge console with HITL" width="900" />
</p>

### Setting · LLM Key 与用量

自带 apikey（掩码展示）+ 日/月/累计 token 看板（图表字体：Noto Sans SC）。

<p align="center">
  <img src="docs/assets/05-settings.png" alt="Settings LLM and usage" width="900" />
</p>

### 对话长什么样

```text
你：做一个霓虹贪吃蛇，方向键控制，带计分。
工坊：run xxx · 已连接
工坊：策划稿已就绪，请在中间面板确认…
—— 确认策划 ——
Gameplay: 移动、收集、计分；失败一键重开
Controls: 方向键 / WASD；空格暂停
Levels: 热身关 · 加速关 · 障碍关
你：[批准继续] → art → code → qa → 右侧试玩
```

---

## For Contributors

### 技术栈

| 层 | 选型 |
|---|---|
| 编排 | LangGraph（检查点 / 人工确认 / 子图） |
| 后端 | Python 3.12 · FastAPI · uv |
| 前端 | React · Vite · TypeScript · Tailwind · TanStack Query · Zustand · MSW |
| 数据 | PostgreSQL · Redis（KV） |
| 消息 | **RabbitMQ + aio-pika**（任务队列 + WS topic） |
| 沙箱 | execute_code（生成期构建） |

### 架构

浏览器只走 **HTTP**（`/api/v1/...`）和 **WebSocket**（`/ws/runs/{run_id}?token=...`），**不直连** Redis 或 RabbitMQ。

```
浏览器 ──HTTP/WS──► FastAPI
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    PostgreSQL     RabbitMQ         Redis
    (主数据)   (任务+WS 事件)   (用量/限流/token/检查点)
                        │
                        ▼
                   Worker 进程
              (`python -m app.messaging.worker`)
```

Forge、登录、Admin 等页面依赖 **OpenAPI 契约** 与 **WS 事件 envelope**（[docs/10](docs/10-contract-and-parallel-dev.md) §5）。中间件替换 **不改前端业务代码**。

### 中间件分工（Redis 不能全换 MQ）

| 能力 | 存储 | 说明 |
|---|---|---|
| 邮件 / 生成 run | RabbitMQ direct `gameforge.tasks` | Worker 消费 |
| 工坊 WS 进度 | RabbitMQ topic `gameforge.ws` | API WS 按 `run.{id}` 订阅 |
| 用量 / 限流 / token / 检查点 | Redis | KV，非队列 |

pytest 默认 `MESSAGING_BACKEND=memory`（进程内总线），无需 RabbitMQ 容器。

实现见 `backend/app/messaging/`；部署见 [docs/09-deployment.md](docs/09-deployment.md)。

### 文档与契约

- [docs/](docs/) — 功能 / 架构 / 生成 / 托管 / 用量 / 认证 / API / 前端 / 部署
- [docs/10-contract-and-parallel-dev.md](docs/10-contract-and-parallel-dev.md) — **契约圣经**
- [contracts/](contracts/) — `openapi.json` · `CHANGELOG.md` · `INTEGRATION.md`（前后端靠 git 协作，不轮询）

约定见 [CLAUDE.md](CLAUDE.md)。截图资源在 [docs/assets/](docs/assets/)。

### 里程碑（摘要）

| | 前端 | 联调 |
|---|---|---|
| M0–M3 | ✅ enums · types · MSW · 认证 · LLM · 用量 | mock / 可 real |
| M4–M6 | Forge / 人工确认 / 试玩 | mock→可 real（关 `VITE_USE_MOCK`） |
| M7–M8 | 审批后台 | mock→可 real |

---

## License

[MIT](LICENSE)
