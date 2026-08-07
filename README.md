# GameForge-Copilot

🎮 浏览器里做小游戏：用平常话讲规则，生成后马上在网页里玩，改到满意再公开。

> 说完就能玩 · 前后端联调见下方「联调启动」。

<p align="center">
  <img src="docs/assets/01-landing.png" alt="GameForge Landing" width="900" />
</p>

<p align="center">
  <code>描述玩法</code> → <code>确认策划</code> → <code>生成构建</code> → <code>浏览器试玩</code> → <code>提交发布</code>
</p>

<p align="center">
  <a href="#联调启动">联调启动</a> ·
  <a href="#demo-cases">Cases</a> ·
  <a href="#product-ui">UI</a> ·
  <a href="#for-contributors">Contributors</a>
</p>

---

## 联调启动

仓库根目录即本文件所在目录（下文命令均相对仓库根）。

### 准备环境

| 工具 | 用途 | 版本建议 |
|---|---|---|
| [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/) | 前端 | Node 20+，pnpm 9+ |
| [uv](https://docs.astral.sh/uv/) | 后端 Python 依赖与运行 | 最新稳定版 |
| Python | 由 uv 按 `.python-version` 拉取 | **3.12** |
| [Docker](https://docs.docker.com/get-docker/) + Compose | Postgres / Redis / RabbitMQ | 推荐 |

本机没有 Docker 时：需自行安装 Postgres 16、Redis 7、RabbitMQ 3，并改 `backend/.env` 里的连接串。

---

### 首次安装（做一次）

**后端**

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
```

**前端**

```bash
cd frontend
cp .env.example .env    # 默认 VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
pnpm install
```

默认连接串（与 `docker compose` / `backend/.env.example` 一致）：

| 服务 | 地址 |
|---|---|
| Postgres | `postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge` |
| Redis | `redis://localhost:6379/0` |
| RabbitMQ | `amqp://gameforge:gameforge@localhost:5672/`（管理台 http://127.0.0.1:15672） |

---

### 启动（联调时每次）

需要 **1 个基础设施进程 + 3 个终端**（或等价后台进程）。

> Worker 消费 **RabbitMQ**（异步任务 + WS 事件 topic）；**Redis 仍保留** KV（用量 / 限流 / token / 检查点）。前端只连 HTTP / WebSocket。

**基础设施**（仓库根目录，后台运行即可）：

```bash
docker compose up -d postgres redis rabbitmq
```

**终端 1 — API**

```bash
cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**终端 2 — Worker**（邮件 + 生成任务；缺它注册验证与 run 都不会执行）

```bash
cd backend && uv run python -m app.messaging.worker
```

**终端 3 — 前端**

```bash
cd frontend && pnpm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)

**自检**

| 检查项 | 地址 |
|---|---|
| API 存活 | [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz) |
| DB / Redis / RabbitMQ 就绪 | [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready) → 三项均为 `true` |
| OpenAPI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| 前后端冒烟 | `cd frontend && pnpm smoke:real`（需 API 已起） |

**说明**

- `LLM_APIKEY_ENCRYPTION_KEY` 可留空（联调环境从 `JWT_SECRET` 派生）；生产必须单独配置。
- `SMTP_*` 留空时，验证/重置邮件打到 **Worker 终端**（`[dev-email] ...`），不会真发信。
- 沙箱默认 `SANDBOX_BACKEND=local`（子进程），不强制 Docker 沙箱镜像。

---

### 联调验收（认证优先）

1. **注册** → Worker 终端 `[dev-email]` 取验证链接 → 完成邮箱验证。
2. **登录** → 未验证会进设置页；已验证进游戏列表。
3. **忘记密码 / 重置**（`/forgot-password`、`/reset-password?token=`）→ 登录态改密（Setting）。
4. 认证通过后：配置 LLM → 工坊生成 → Admin 审批（需 admin 角色）。

管理员：在库中将用户 `role` 设为 `admin`。

---

### 可选：整栈 Docker Compose

API + Worker 也放进容器（前端仍建议本机 `pnpm dev` 热更新）：

```bash
docker compose up -d postgres redis rabbitmq backend worker
```

API：[http://127.0.0.1:8000](http://127.0.0.1:8000)

compose 里 backend 使用 `backend/.env.example` 作为 `env_file`，并覆盖容器网络内的 `DATABASE_URL` / `REDIS_URL`。日常改配置优先改本机 `backend/.env`。

容器内若需补迁移：

```bash
docker compose exec backend uv run alembic upgrade head
```

---

### 端口速查

| 服务 | 地址 |
|---|---|
| 前端 Vite | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000（前缀 `/api/v1`） |
| Postgres | `localhost:5432` |
| Redis | `localhost:6379` |
| RabbitMQ | `localhost:5672` |
| RabbitMQ 管理台 | http://127.0.0.1:15672（gameforge / gameforge） |
| 本地产物 | `backend/.hosting/`（`HOSTING_ROOT`） |

---

### 常见问题

| 现象 | 处理 |
|---|---|
| 跨域 / 注册登录无请求 | 后端 `CORS_ORIGINS` 须含你实际打开的前端地址（默认 5173；5173 被占用时 Vite 会用 5174，需一并加入）；用 `127.0.0.1` 打开，不要混用 `localhost`。改 `.env` 后重启 API。 |
| `/ready` 某项为 false | 确认 `docker compose up -d postgres redis rabbitmq` 已跑，检查 `backend/.env` 连接串。 |
| 注册后没有验证邮件 | Worker 是否在跑；看 Worker 终端 `[dev-email]`。 |
| 发起生成一直不动 | Worker 是否在跑；设置里已配可用 LLM；邮箱已验证。 |
| `alembic` / `uv` 找不到 | 在 `backend/` 下执行，先 `uv sync`。 |

---

## Demo Cases

落地页展示的三条典型玩法路径（注册登录后可在工坊自行复现）。完整卡片见下图。

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

截图来自本地 `pnpm dev` 联调真实后端（2026-08）。

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
| 前端 | React · Vite · TypeScript · Tailwind · TanStack Query · Zustand |
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

Forge、登录、Admin 等页面依赖 **OpenAPI 契约** 与 **WS 事件 envelope**（[docs/10](docs/10-contract-and-parallel-dev.md) §5）。

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
- [contracts/](contracts/) — `openapi.json` · `CHANGELOG.md` · `INTEGRATION.md`

约定见 [CLAUDE.md](CLAUDE.md)。截图资源在 [docs/assets/](docs/assets/)。

### 里程碑（摘要）

| 模块 | 状态 |
|---|---|
| M0–M3 认证 · LLM 配置 · 用量 | ✅ 前后端联调 |
| M4–M6 游戏 CRUD · Forge · HITL · 试玩 | ✅ 前后端联调 |
| M7–M8 发布审批 · 管理后台 | ✅ 前后端联调 |

---

## License

[MIT](LICENSE)
