# GameForge-Copilot

[English](README.md) | [简体中文](README.zh-CN.md)

GameForge-Copilot 是一个可自行部署的 Web 工作区，用于将游戏想法转变为可直接试玩的 HTML 游戏。用自然语言描述游戏，查看生成的设计方案，然后在浏览器中试玩结果。

![GameForge 首页](docs/assets/home.png)

## 项目介绍

项目由 React 工作区、FastAPI 后端、异步 Worker 和可配置的 LLM Provider 组成，采用人工参与的工作流：在继续素材、代码生成、沙箱检查与浏览器试玩前，先确认设计方案。

## 试玩演示

完整试玩流程视频将在当前游戏生成功能合入后，以后续媒体更新补充。录制流程和文件名见[媒体清单](docs/assets/README.md)。

## 核心功能

- 通过自然语言描述游戏，并在结构化设计确认后开始生成。
- 通过 WebSocket 实时展示 Forge 进度，支持暂停、继续、取消和重试。
- 内置素材选择、HTML 游戏生成、沙箱校验和自动化浏览器试玩。
- 私有草稿预览、版本历史、版本切换和 HTML 版本下载。
- 发布申请与管理员审核队列，用于公开游戏。
- 无需 LLM 配置即可试玩官方示例游戏；已验证用户可将示例 Fork 为自己的草稿。
- 可配置 OpenAI、Anthropic 与 OpenAI Compatible Provider，并记录每位用户的用量。

## 工作方式

```text
Describe game
  -> Confirm design
  -> Generate game
  -> Play in browser
  -> Download or publish
```

Worker 使用 LangGraph 编排方案设计、素材选择、代码生成和 QA。生成产物按游戏版本保存，并作为独立 HTML 预览提供。

## 截图

| 首页 | 可试玩游戏 |
| --- | --- |
| ![GameForge 首页](docs/assets/home.png) | ![GameForge 中运行的官方霓虹贪吃蛇](docs/assets/playable-snake.png) |

## 快速开始

### 前置条件

- Docker Desktop with Docker Compose
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and [pnpm](https://pnpm.io/)

### 1. 启动依赖服务

```bash
docker compose up -d postgres redis rabbitmq
```

### 2. 配置并初始化后端

```bash
cp backend/.env.example backend/.env
cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_official_games
```

### 3. 在两个终端中分别运行 API 与 Worker

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd backend
uv run python -m app.messaging.worker
```

### 4. 运行前端

```bash
cp frontend/.env.example frontend/.env
cd frontend
pnpm install
pnpm dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)，并通过 [http://127.0.0.1:8000/ready](http://127.0.0.1:8000/ready) 确认服务已就绪。

不要提交任一 `.env` 文件。拉取包含后端迁移的更新后，请再次运行 `cd backend && uv run alembic upgrade head`。

## LLM 配置

1. 注册并验证账号。
2. 打开 **Settings**，添加 LLM 配置。
3. 选择 OpenAI、Anthropic 或 OpenAI Compatible，并填写对应 Provider 所需的模型与 API 信息。
4. 将其中一个配置设为默认，然后打开 Forge 开始创建游戏。

凭据会由后端加密，且不会被写入生成的游戏产物。生成需要 LLM 配置；官方示例游戏无需配置即可试玩。

## 架构

```text
React + Vite
     |
FastAPI API <-> PostgreSQL / Redis / RabbitMQ
     |
Forge worker (LangGraph)
     |
LLM provider -> sandbox + browser playtest -> versioned HTML hosting
```

## 项目结构

```text
backend/     FastAPI API、Forge 图、Worker、迁移和测试
frontend/    React + TypeScript 应用
contracts/   OpenAPI 快照和集成契约说明
docker/      Backend、Worker 和 sandbox 镜像
docs/        产品与工程文档
```

## 路线图

- 根据后续修改请求生成第二个游戏版本。
- 为生成的游戏上传用户美术素材和音效。
- 更丰富的封面图片与公开游戏发现体验。
- 更多部署目标与运维工具。

## 参与贡献

从 `main` 创建分支，保持改动聚焦，并为行为变化提供测试。提交 Pull Request 前请运行相关检查：

```bash
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && pnpm test && pnpm lint && pnpm build
```

API 契约生成在 `contracts/openapi.json`；API 变更后，使用 `cd backend && uv run python -m app.export_openapi > ../contracts/openapi.json` 刷新，然后运行 `cd frontend && pnpm gen:api`。

## 许可证

本项目使用 [MIT License](LICENSE) 发布。
