# GameForge-Copilot

🎮 浏览器里做小游戏：用平常话讲规则，生成后马上在网页里玩，改到满意再公开。

> 说完就能玩 · 环境变量与启动顺序见下方「环境变量配置」「从 0 到 1 启动」。

<p align="center">
  <img src="docs/assets/01-landing.png" alt="GameForge Landing" width="900" />
</p>

<p align="center">
  <code>描述玩法</code> → <code>确认策划</code> → <code>生成构建</code> → <code>浏览器试玩</code> → <code>提交发布</code>
</p>

<p align="center">
  <a href="#复制执行">复制执行</a> ·
  <a href="#环境变量配置">Env</a> ·
  <a href="#从-0-到-1-启动">启动</a> ·
  <a href="#docker-部署">Docker</a> ·
  <a href="#demo-cases">Cases</a> ·
  <a href="#product-ui">UI</a> ·
  <a href="#for-contributors">Contributors</a>
</p>

---

## 📋 Windows 完整启动顺序

### 第一步：启动 Docker 基础设施

```bash
# 在项目根目录执行
docker compose up -d postgres redis rabbitmq
```

### 第二步：初始化后端（仅首次）
```bash
cd backend
pip install uv
uv sync
uv run alembic upgrade head  # 创建数据库表结构，alembic.ini
uv run python -m scripts.seed_official_games  # 官方试玩 + 试用账号 demo@gameforge.dev
cd ..
```

### 第三步：启动后端 API（终端1）
```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 第四步：启动 Worker（终端2 - 新开CMD/PowerShell）
```bash
cd backend
uv run python -m app.messaging.worker
```

### 第五步：启动前端（终端3 - 新开CMD/PowerShell）
```bash
cd frontend
pnpm install  # 仅首次
pnpm run dev
```

### 第六步：验证服务
```bash
# 检查所有服务是否就绪
curl http://127.0.0.1:8000/ready

# 浏览器访问
# 前端：http://127.0.0.1:5173
# 后端API文档：http://127.0.0.1:8000/docs
# RabbitMQ管理台：http://127.0.0.1:15672  
# 账号密码都是：gameforge 
```

### 清理缓存+残留任务
curl -X POST "http://127.0.0.1:8000/api/v1/dev/reset?confirm=FLUSH"


---

## ⚠️ Windows 特别注意

| 问题 | 解决方案 |
|------|---------|
| **curl 命令不存在** | 用浏览器访问 `http://127.0.0.1:8000/ready` 代替 |
| **uv 命令找不到** | 安装：`pip install uv` |
| **pnpm 命令找不到** | 安装：`npm install -g pnpm` |
| **端口被占用** | 关闭占用进程，或改端口配置 |
| **Docker Desktop 未启动** | 先打开 Docker Desktop 应用 |

---

## 🛑 停止所有服务

```bash
# 停止 Docker 容器
docker compose down

# 停止本地进程（在各自终端按 Ctrl+C）
```

---

## 环境变量配置

联调只需维护 **两个 `.env` 文件**，均从各自 `.env.example` 复制而来：

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

| 文件 | 谁读 | 作用 |
|---|---|---|
| `backend/.env` | FastAPI、Worker、Alembic | 数据库、消息队列、JWT、邮件、CORS、沙箱等 |
| `frontend/.env` | Vite 构建 / 开发服务器 | 前端请求的后端 API 地址 |

> **不要**把真实密钥提交进 Git。`.env` 已在 `.gitignore` 中；改完 env 后需 **重启** 对应进程（API / Worker / 前端 dev server）才会生效。

### 前端 `frontend/.env`

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | 所有 REST 请求前缀；**不含**末尾 `/` |
| `VITE_HOSTING_BASE_URL` | （可选） | 试玩页 `/play`、`/draft` 的静态根；默认从 API 地址去掉 `/api/v1` |
| `VITE_WS_BASE_URL` | （可选） | WebSocket 根；默认由 hosting 的 `http→ws` 推导 |

联调一般 **只改 `VITE_API_BASE_URL`**，且须与后端实际监听地址一致（本机默认 `127.0.0.1:8000`）。

### 后端 `backend/.env`（按组）

**① 基础设施连接**（与 `docker compose` 默认账号一致）

| 变量 | 本机联调值 |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `RABBITMQ_URL` | `amqp://gameforge:gameforge@localhost:5672/` |
| `MESSAGING_BACKEND` | `rabbitmq`（pytest 用 `memory`，无需 RabbitMQ 容器） |

**② 与前端地址相关的两项（最容易配错）**

| 变量 | 作用 | 联调建议 |
|---|---|---|
| `CORS_ORIGINS` | 允许浏览器跨域的来源列表 | 必须包含你在地址栏 **实际打开** 的前端 URL |
| `FRONTEND_BASE_URL` | 验证 / 重置邮件里的页面链接前缀 | 与浏览器打开的前端地址一致 |

**③ 安全与邮件**

| 变量 | 联调 | 生产 |
|---|---|---|
| `JWT_SECRET` | 可先用 example 占位 | **必须**换成强随机串 |
| `LLM_APIKEY_ENCRYPTION_KEY` | 可留空（从 `JWT_SECRET` 派生） | **必须**单独配置 Fernet key |
| `SMTP_*` | 留空 → 验证码打印在 **Worker 终端** `[dev-email]` | 填真实 SMTP |

**④ 其他常用项**

| 变量 | 说明 |
|---|---|
| `HOSTING_ROOT` | 游戏产物目录，默认 `.hosting`（相对 `backend/`） |
| `SANDBOX_BACKEND` | 联调 `local`（子进程）；Docker 整栈为 `docker` |
| `ENV` / `LOG_LEVEL` | 开发 `development` + `INFO` |

完整字段见 [`backend/.env.example`](backend/.env.example)。

### 5173 与 5174：什么时候用哪个？

| 端口 | 角色 | 何时出现 |
|---|---|---|
| **5173** | 前端 Vite 开发服务器（默认） | `frontend/vite.config.ts` 固定 `port: 5173`；正常联调打开 [http://127.0.0.1:5173](http://127.0.0.1:5173) |
| **5174** | 备用前端端口 | 仅当你 **手动** 改端口（如 `vite --port 5174` 或改 `vite.config.ts`）时使用；**不会**因 5173 被占用而自动切换（项目启用了 `strictPort: true`，5173 被占会直接启动失败） |
| **8000** | 后端 API | 前端 `VITE_API_BASE_URL` 指向此处 |
| **5432 / 6379 / 5672** | Postgres / Redis / RabbitMQ | 由 Docker Compose 映射到本机 |

**三条硬性约定：**

1. **浏览器地址、 `CORS_ORIGINS`、 `FRONTEND_BASE_URL` 三者保持一致**（含 `http://`、主机名、端口）。
2. **不要混用 `127.0.0.1` 与 `localhost`**——example 默认用 `127.0.0.1`，请全程统一。
3. 若改用 5174（或其它端口），需同时改：`vite` 端口、`backend/.env` 的 `CORS_ORIGINS` 与 `FRONTEND_BASE_URL`，然后重启 API 与 Worker。

`.env.example` 里预填了 5173 与 5174 四套 CORS 来源，是为「偶尔手动换端口」预留；**默认联调只用 5173**。

### 无 Docker 时

自行安装 Postgres 16、Redis 7、RabbitMQ 3 后，只改 `backend/.env` 中上述三条连接串即可；启动顺序不变。

---

## 从 0 到 1 启动

下文命令均相对于 **仓库根目录**（本 README 所在目录）。

### 准备工具

| 工具 | 用途 | 版本建议 |
|---|---|---|
| [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/) | 前端 | Node 20+，pnpm 9+ |
| [uv](https://docs.astral.sh/uv/) | 后端 Python | 最新稳定版 |
| Python | 由 uv 按 `.python-version` 拉取 | **3.12** |
| [Docker](https://docs.docker.com/get-docker/) + Compose | Postgres / Redis / RabbitMQ | 强烈推荐 |

### 启动顺序总览

```
① 基础设施 (Postgres + Redis + RabbitMQ)
        ↓
② 后端首次：uv sync + 数据库迁移 + 官方预置游戏 seed（仅第一次）
        ↓
③ 后端 API (uvicorn :8000)
        ↓
④ Worker (消费 RabbitMQ：邮件 + 生成任务)
        ↓
⑤ 前端首次：pnpm install（仅第一次）
        ↓
⑥ 前端 dev (Vite :5173)
        ↓
⑦ 浏览器打开 → 自检 /ready → 注册验收
```

> Worker 消费 **RabbitMQ**（异步任务 + WS 事件）；**Redis** 仍负责用量 / 限流 / token / 检查点。浏览器 **只** 连 HTTP 与 WebSocket，不直连 Redis 或 RabbitMQ。

---

### 步骤 ① — 基础设施（每次联调最先执行）

在仓库根目录：

```bash
docker compose up -d postgres redis rabbitmq
```

等待健康检查通过（约十几秒）。可用 `docker compose ps` 确认三个服务均为 `healthy`。

| 服务 | 本机地址 | 默认账号 |
|---|---|---|
| Postgres | `localhost:5432` | `gameforge` / `gameforge`，库名 `gameforge` |
| Redis | `localhost:6379` | 无密码，DB `0` |
| RabbitMQ | `localhost:5672` | `gameforge` / `gameforge` |
| RabbitMQ 管理台 | [http://127.0.0.1:15672](http://127.0.0.1:15672) | 同上 |

---

### 步骤 ② — 后端从 0 到 1（首次克隆做一次）

```bash
cd backend
cp .env.example .env          # 按需改连接串，见上文「环境变量配置」
uv sync                       # 安装 Python 依赖
uv run alembic upgrade head   # 建表 / 升级 schema
uv run python -m scripts.seed_official_games   # 写入/修复 3 款官方试玩游戏（幂等、自愈，可重复执行）
cd ..
```

之后若拉取了含新迁移的代码，在 **`backend/`** 下再执行一次 `uv run alembic upgrade head` 即可。

**官方预置游戏（Batch A · R1）** 不随迁移自动写入，**新环境 / 空库必须跑 seed**。终端用户无感知；部署与联调者需知道这一步。写入内容：3 款 `published` 游戏（`official-neon-snake` 等）+ `backend/.hosting/` 下静态产物，owner 为系统账号 `official@gameforge.internal`（不可登录）。

> **改官方试玩游戏**：编辑源文件 `backend/scripts/official_assets/*.html`，再重跑 `uv run python -m scripts.seed_official_games` 即更新线上试玩（**勿直接改 `.hosting/`**——那是构建产物，会被覆盖）。3 款游戏用**固定 UUID**（`...0000000000a1/a2/a3`），重建 DB 也不会让产物漂移成孤儿；seed 遇到历史随机 UUID 的旧行会自愈迁移。

---

### 步骤 ③④ — 后端日常启动（每次联调，两个终端）

**须先完成 ①**；API 与 Worker 都依赖 Postgres / Redis / RabbitMQ。

**终端 A — API**

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**终端 B — Worker**（与 API 无严格先后，但 **必须在测注册 / 生成之前起来**）

```bash
cd backend
uv run python -m app.messaging.worker
```

缺 Worker 时：注册验证码不会出现、Forge 生成会一直卡住。

---

### 步骤 ⑤⑥ — 前端从 0 到 1

**首次（克隆后做一次）：**

```bash
cd frontend
cp .env.example .env
pnpm install
cd ..
```

**每次联调（建议 API 已启动后再开前端）：**

```bash
cd frontend
pnpm run dev
```

终端出现 `Local: http://127.0.0.1:5173/` 后，用 **同一主机名** 打开（推荐 `127.0.0.1`，与 `.env` 一致）。

---

### 步骤 ⑦ — 自检与联调验收

| 检查项 | 地址 / 命令 | 期望 |
|---|---|---|
| API 存活 | [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz) | `ok` |
| 依赖就绪 | [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready) | `postgres` / `redis` / `rabbitmq` 均为 `true` |
| OpenAPI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | 可浏览 |
| 官方游戏列表 | [http://127.0.0.1:8000/api/v1/official-games](http://127.0.0.1:8000/api/v1/official-games) | `data` 含 3 项（需已 seed） |
| 官方试玩 | [http://127.0.0.1:8000/play/official-neon-snake](http://127.0.0.1:8000/play/official-neon-snake) | 返回 HTML，无需登录 |
| 前后端冒烟 | `cd frontend && pnpm smoke:real` | 通过（需 API 已起） |

**功能验收（建议顺序）：**

0. **官方示例（无需 LLM Key）** → 浏览器打开 `/play/official-neon-snake`，或 `GET /api/v1/official-games` 见 3 款；登录后可 `POST /api/v1/games/fork/official-neon-snake` Fork 为自己的 draft（不消耗 LLM）。
1. **注册** → 在 Worker 终端找 `[dev-email]` 验证码 → 完成邮箱验证。
2. **登录** → 未验证进设置页；已验证进游戏列表。
3. **忘记密码 / 重置** → 登录态可在 Setting 改密。
4. 认证通过后：Setting 配置 LLM → 工坊生成 → Admin 审批（管理员初始化见下节）。

### 管理员账号与后台

注册账号默认均为普通用户，系统不预置固定管理员邮箱或密码。首次管理员由有数据库访问权限的运维人员在 `backend/` 下创建或提权：

```bash
# 创建新管理员（交互输入密码）
uv run python -m scripts.create_admin --email admin@example.com

# 将已注册账号提权为管理员（保留原密码）
uv run python -m scripts.create_admin --email user@example.com --promote-existing
```

提权后请退出并重新登录。管理员可从左侧导航或账号菜单进入 `/admin`，进行发布审批、游戏下架/精选、用户与配额管理、用量分析、审计日志和全局设置。前端会隐藏并拦截普通用户的后台入口，后端所有管理接口还会独立校验数据库中的 `role=admin`；系统禁止禁用/删除当前管理员，并确保至少保留一名可用管理员。

> **安全说明：** `create_admin.py` 是仅供运维执行的命令行工具，不是公开 API；当前后端容器镜像也未复制 `backend/scripts/`。不要把生产数据库凭据、服务器终端权限或 `.env` 交给非运维人员。将该脚本加入 `.gitignore` 不能构成安全保护：文件已被 Git 跟踪，且拥有生产数据库写权限的人即使没有脚本也能直接修改角色。

---

## Docker 部署

### 模式 A — 仅基础设施（推荐日常联调）

与上文 ① 相同；API / Worker / 前端在本机跑，便于 `--reload` 与 Vite 热更新：

```bash
docker compose up -d postgres redis rabbitmq
# 然后按「从 0 到 1 启动」步骤 ③～⑥ 在本机起 API、Worker、前端
```

### 模式 B — 后端也容器化

API + Worker 进容器；**前端仍建议本机** `pnpm dev`：

```bash
docker compose up -d postgres redis rabbitmq backend worker
```

| 项 | 说明 |
|---|---|
| API 地址 | [http://127.0.0.1:8000](http://127.0.0.1:8000) |
| env 来源 | compose 读 `backend/.env.example`，并 **覆盖** 容器内 `DATABASE_URL` / `REDIS_URL` / `RABBITMQ_URL` |
| 日常改配置 | 优先改本机 `backend/.env`；容器模式需同步改 compose 或重建镜像 |
| 沙箱 | 容器内默认 `SANDBOX_BACKEND=docker`，需本机 Docker 与 `docker.sock` |

首次或迁移变更后，在容器内补迁移与 seed：

```bash
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m scripts.seed_official_games
```

### 模式 C — 构建沙箱镜像（可选）

Forge 在 Docker 沙箱中执行生成代码时需要：

```bash
docker compose --profile build-sandbox build sandbox
```

### 端口速查

| 服务 | 地址 |
|---|---|
| 前端 Vite | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000（REST 前缀 `/api/v1`） |
| Postgres | `localhost:5432` |
| Redis | `localhost:6379` |
| RabbitMQ AMQP | `localhost:5672` |
| RabbitMQ 管理台 | http://127.0.0.1:15672 |
| 本地产物目录 | `backend/.hosting/`（`HOSTING_ROOT`） |

---

### 常见问题

| 现象 | 处理 |
|---|---|
| 前端 dev 报端口占用 | 5173 被占且 `strictPort: true` 会直接失败；释放占用进程或改 `vite.config.ts` 端口，并同步 `CORS_ORIGINS` / `FRONTEND_BASE_URL` |
| 跨域 / 登录注册无响应 | `CORS_ORIGINS` 须含浏览器实际 URL；勿混用 `127.0.0.1` 与 `localhost`；改 `.env` 后 **重启 API** |
| `/ready` 某项为 `false` | 确认 ① 三个容器 healthy；检查 `backend/.env` 连接串是否指向 `localhost` |
| 注册后没有验证码 | Worker 终端是否在跑；查看 `[dev-email]` 输出 |
| 工坊生成一直不动 | Worker 是否运行；Setting 是否已配可用 LLM；邮箱是否已验证 |
| Worker 宕机 / 想清空队列或缓存 | 见下方「本地调试工具」；`ENV=development` 时可用 |
| 刷新页面后 Forge 任务「消失」 | 后端仍在跑；重进工坊会自动恢复 WS + 事件回放（需 API/Worker 已更新） |
| 官方游戏列表为空 / `/play/official-*` 404 | 是否执行 `uv run python -m scripts.seed_official_games`（migrate 不会自动写入） |
| `alembic` / `uv` 找不到 | 命令须在 `backend/` 下执行，且已 `uv sync` |

### 本地调试工具（仅 `ENV=development`）

开发环境下 API 提供 **Redis 清理、RabbitMQ 队列 purge、stuck run 重投** 等端点，方便 Worker 崩溃或反复联调时恢复现场。生产环境（`ENV!=development`）一律返回 403。

**前置：** `backend/.env` 中 `ENV=development`，改代码后重启 API。

#### 查看状态

```bash
# Redis 各 scope 键数量 + 队列深度
curl http://127.0.0.1:8000/api/v1/dev/runtime/status

# 仅看 RabbitMQ 队列 gameforge.worker
curl http://127.0.0.1:8000/api/v1/dev/queue/stats
```

#### Worker 宕机后恢复 run（推荐）

不清数据，只把任务重新丢进队列：

```bash
# 1. 重启 Worker
cd backend && uv run python -m app.messaging.worker

# 2. 重投 stuck run（根据 DB 状态 + Redis 检查点选 execute_run / resume_run）
curl -X POST http://127.0.0.1:8000/api/v1/dev/runs/{run_id}/requeue
```

#### 清空消息队列

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/dev/queue/purge?confirm=FLUSH"
```

#### 清空 Redis（按 scope）

破坏性操作均需 `"confirm":"FLUSH"`。

```bash
# 清空所有 run 相关：事件回放、检查点、暂停/取消标志、HITL 锁
curl -X POST http://127.0.0.1:8000/api/v1/dev/redis/flush \
  -H "Content-Type: application/json" \
  -d '{"scopes":["forge"],"confirm":"FLUSH"}'

# 只清某一个 run
curl -X POST http://127.0.0.1:8000/api/v1/dev/redis/flush \
  -H "Content-Type: application/json" \
  -d '{"scopes":["forge"],"run_id":"YOUR-RUN-UUID","confirm":"FLUSH"}'

# 清空除 refresh token 外的常见缓存（用量、限流、quota、analytics 等）
curl -X POST http://127.0.0.1:8000/api/v1/dev/redis/flush \
  -H "Content-Type: application/json" \
  -d '{"scopes":["all_ephemeral"],"confirm":"FLUSH"}'
```

| Redis scope | 清除内容 |
|---|---|
| `forge` | `run:events:*` / `run:ckpt:*` / `run:ctrl:*` / `run:hitl:*` |
| `usage` | 用量统计 |
| `analytics` | 试玩 PV/UV |
| `rate_limits` | `rl:*` |
| `quota` | 配额覆盖与告警 |
| `dev_helpers` | 验证码、`oauth:state` |
| `models_cache` | LLM 模型列表缓存 |
| `refresh_tokens` | 所有 refresh token（**会登出全部用户**） |
| `all_ephemeral` | 以上除 `refresh_tokens` 外全部 |
| `pattern` | 自定义，需额外传 `"pattern":"run:events:*"` |

**命令行等价操作（不用 API）：**

```bash
redis-cli FLUSHDB                                    # 清空当前 Redis DB（最暴力）
redis-cli --scan --pattern 'run:*' | xargs redis-cli DEL
rabbitmqctl purge_queue gameforge.worker             # 或管理台 http://127.0.0.1:15672
```

#### Run 持久化（刷新 / 跳转不丢任务）

- 后端：Redis 环形缓冲 `run:events:{run_id}`，WS 重连时回放；`GET /api/v1/me/runs/active` 列出进行中 run。
- 前端：sessionStorage 记住 `{gameId, runId}`，回到 Forge 自动重连 WS；顶栏 **ActiveRunBanner** 可一键返回。

### 日志落盘（`logs/`）

本地开发时，按 **北京时间当天** 分目录，三类进程各写一份 JSON 行日志（已在 `.gitignore`）：

```text
logs/
└── 26-08-07/          # YY-MM-DD（北京时间）
    ├── backend.log    # uvicorn API
    ├── worker.log     # RabbitMQ worker
    └── frontend.log   # pnpm dev 浏览器
```

每条日志的 `ts` 字段为 **北京时间**（`+08:00`）。

**查看最近错误：**

```bash
DAY=$(TZ=Asia/Shanghai date +%y-%m-%d)
tail -f logs/$DAY/worker.log
grep exc_info logs/$DAY/worker.log
```

配置（`backend/.env`）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_DIR` | （空） | 空 = `autoGame/logs/`；`-` = 仅 stdout（pytest 用） |

改 env 或代码后需 **重启 API / Worker**；前端 dev server 重启后才会新建 `frontend.log`。

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
- [docs/11-experience-requirements.md](docs/11-experience-requirements.md) — 体验增强需求（2026-08-07）
- [docs/12-experience-task-breakdown.md](docs/12-experience-task-breakdown.md) — 前后端任务拆分 + Agent 提示词
- [docs/10-contract-and-parallel-dev.md](docs/10-contract-and-parallel-dev.md) — **契约圣经**
- [contracts/](contracts/) — `openapi.json` · `CHANGELOG.md` · `INTEGRATION.md`

约定见 [CLAUDE.md](CLAUDE.md)。截图资源在 [docs/assets/](docs/assets/)。

### 后端自测（Batch A · 官方游戏与工坊 API）

在 `backend/` 下，迁移 + seed 后可用 curl 快速验收（Fork 需先注册并验证邮箱，替换 `<token>`）：

```bash
# 官方列表（无需登录）
curl -s http://127.0.0.1:8000/api/v1/official-games | jq .

# 试玩页（浏览器打开亦可）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/play/official-neon-snake

# Fork 为当前用户 draft（需 Bearer + 已验证）
curl -s -X POST http://127.0.0.1:8000/api/v1/games/fork/official-neon-snake \
  -H "Authorization: Bearer <token>"
```

完整单测：`cd backend && uv run pytest -q`。契约见 [docs/10](docs/10-contract-and-parallel-dev.md)（含 `POST /runs/{id}/retry`、`POST /games/{id}/versions/{v}/activate` 等 Batch A 端点）。

### 里程碑（摘要）

| 模块 | 状态 |
|---|---|
| M0–M3 认证 · LLM 配置 · 用量 | ✅ 前后端联调 |
| M4–M6 游戏 CRUD · Forge · HITL · 试玩 | ✅ 前后端联调 |
| M7–M8 发布审批 · 管理后台 | ✅ 前后端联调 |

---

## License

[MIT](LICENSE)
