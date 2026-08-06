# GameForge-Copilot

> 用户在 Web 端用自然语言多轮对话，从 0 到 1 设计并发布一款在线可运行的小游戏。

GameForge-Copilot 是一个生产级的 Web 应用服务（非手机端、非微信小游戏）。用户描述"我想设计一个 XX 游戏"，系统通过自研编排框架驱动多角色 Agent 生成可运行的游戏代码，产物托管上线即可玩；支持发布审批、多租户 token 用量计量、用户自带 LLM apikey。

## 核心能力

- **对话式游戏生成**：多轮对话，从需求到可运行游戏，Agent 自主生成代码，不在业务代码中硬编码任何游戏逻辑约束。
- **在线可玩**：生成的游戏作为静态产物托管，按 slug 路由直接访问运行。
- **发布审批流**：未发布的游戏仅创建者可见（管理员也不可见）；发布后由管理员审批、上架、下架。
- **多租户用量计量**：基于 LLM 响应真实 token 用量，Redis 累计系统总量与每用户用量，用于配额与限流。
- **用户自带 LLM Key**：provider/model/apikey 在 Web 端 setting 由用户自配，系统不绑死任何厂商。
- **生产级账号体系**：邮箱注册 + 验证 + JWT 认证 + 用户/管理员双角色。

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 编排框架 | LangGraph | 检查点/可恢复长任务、HITL 审批中断、子图多角色、流式、LLM 无关 |
| LLM | Claude（默认，可换） | provider 抽象，用户自带 key |
| 后端 | Python 3.12 + FastAPI + uv | async 契合 IO 密集；沙箱资产同栈可复用 |
| 前端 | React + Vite + TypeScript + Tailwind + shadcn/ui | 轻量、生态大、便于嵌入游戏产物 |
| 数据库 | PostgreSQL | 用户/游戏/发布记录等主数据 |
| 缓存/计量 | Redis | token 用量、会话、限流、检查点 KV |
| 沙箱 | execute_code sandbox（资源分级） | Agent 生成期代码执行与产物构建 |
| 部署 | Docker + GitLab CI | 可复现、生产级 |

## 架构一览

```
[Web 前端] ──HTTP/WS──▶ [FastAPI 后端]
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
   [LangGraph 编排]   [认证/权限]      [游戏产物托管]
   ├ 策划子图          └ 用户/管理员       └ 静态资源 /slug
   ├ 美术子图
   ├ 代码子图 ──▶ [沙箱 execute_code]  生成 → 构建 → 托管
   └ 质检子图
        │
        ▼
   [LLM Provider 抽象]  ◀── 用户 Web 端自配 apikey
        │
        ▼
   [Redis 用量计量]   [PostgreSQL 主数据]
```

详见 [docs/02-architecture.md](docs/02-architecture.md)。

## 快速开始

> 代码尚未实现。以下为规划的目标启动方式，落地时以此为准。

```bash
# 后端
cd backend
uv sync
cp .env.example .env   # 填 DB/Redis/默认 LLM 等
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 前端
cd frontend
pnpm install
pnpm dev

# 依赖（Docker）
docker compose up -d postgres redis worker   # sandbox 镜像由后端按 run 拉起，无需常驻
```

访问 `http://localhost:5173`，注册账号，在 setting 上传 LLM apikey，开始设计游戏。

## 文档

完整设计文档在 [docs/](docs/)：

- [01-features.md](docs/01-features.md) — 功能清单
- [02-architecture.md](docs/02-architecture.md) — 整体架构
- [03-game-generation.md](docs/03-game-generation.md) — 游戏生成编排
- [04-hosting-and-publish.md](docs/04-hosting-and-publish.md) — 产物托管与发布审批
- [05-tenant-usage-llm.md](docs/05-tenant-usage-llm.md) — 多租户/用量计量/LLM 配置
- [06-auth-and-security.md](docs/06-auth-and-security.md) — 认证与权限
- [07-api-and-data-model.md](docs/07-api-and-data-model.md) — API 与数据模型
- [08-frontend.md](docs/08-frontend.md) — 前端
- [09-deployment.md](docs/09-deployment.md) — 部署与运维
- [10-contract-and-parallel-dev.md](docs/10-contract-and-parallel-dev.md) — 前后端契约与并行开发

协作目录 [contracts/](contracts/) — 前后端接口契约与协作流程（openapi.json + CHANGELOG + INTEGRATION），前后端 agent 靠 git 通信、不轮询。

## 开发约定

见 [CLAUDE.md](CLAUDE.md)。

## License

待定。
