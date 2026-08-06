# CLAUDE.md

> 本文件给在本仓库工作的 AI 助手（Claude 等）提供项目约定。务必先读。

## 项目定位

GameForge-Copilot：Web 端多轮对话 → 从 0 到 1 生成并发布在线可运行小游戏。生产级服务，不是 demo。详见 [README.md](README.md) 与 [docs/](docs/)。

## 目录结构（规划）

```
autoGame/
├─ README.md
├─ CLAUDE.md
├─ docs/                # 设计文档（已存在）
├─ backend/             # FastAPI 后端
│  ├─ app/
│  │  ├─ main.py        # 入口
│  │  ├─ api/           # 路由
│  │  ├─ auth/          # 认证/权限
│  │  ├─ forge/         # 游戏生成编排（LangGraph）
│  │  │  ├─ graph.py    # 主状态图
│  │  │  ├─ subgraphs/  # 策划/美术/代码/质检子图
│  │  │  ├─ skills/     # 生成 skill/prompt 体系
│  │  │  └─ sandbox.py  # 沙箱 execute_code 封装
│  │  ├─ hosting/       # 游戏产物托管与版本
│  │  ├─ publish/       # 发布审批工作流
│  │  ├─ usage/         # token 用量计量（Redis）
│  │  ├─ llm/           # LLM provider 抽象（用户自带 key）
│  │  ├─ models/        # ORM 模型
│  │  ├─ schemas/       # Pydantic schema
│  │  ├─ core/          # 配置/依赖/安全
│  │  └─ ws/            # 流式/事件总线
│  ├─ alembic/          # 迁移
│  ├─ tests/
│  └─ pyproject.toml    # uv 管理
├─ frontend/            # React + Vite + TS
│  ├─ src/
│  │  ├─ pages/         # 设计/展示/管理后台
│  │  ├─ components/
│  │  ├─ api/
│  │  ├─ stores/
│  │  └─ ws/
│  └─ package.json      # pnpm
└─ docker/              # Dockerfile / compose
```

## 编码约定

- **语言**：始终用简体中文写文档、注释、commit message 主体、Issue/PR；变量/函数名用英文。
- **风格**：遵循 DRY/KISS/SOLID/YAGNI；单函数 ≤ 50 行，单文件 > 500 行拆分。
- **后端**：Python 3.12，类型注解必填；async 优先（IO 密集：LLM/沙箱/DB/Redis/邮件）；依赖 uv。
- **前端**：TS 严格模式；pnpm；组件优先 shadcn/ui，避免重复造轮子。
- **安全**：禁硬编码密钥；外部输入必校验；错误显式处理，禁止静默吞异常。
- **测试**：公共逻辑写完同步补测试，放 `backend/tests/`；改动公共逻辑同步改测试。
- **文档**：架构/方案文档进 `docs/`，不进代码目录。
- **Git**：GitHub Flow，从 `main` 拉分支、PR 合回；commit 走 Conventional Commits（feat/fix/refactor/docs/test/chore），原子提交。

## 关键架构约束

- **编排用 LangGraph**，不自研 agent loop，不直接套 Claude Agent SDK 当全套 harness。
- **LLM provider 不硬编码**：用户在 Web 端 setting 自配 provider/model/apikey；后端 `llm/` 抽象一层，按用户配置动态构造客户端。
- **token 用量取 LLM 响应 `usage` 字段**（input_tokens/output_tokens），写 Redis；不估算。
- **游戏产物静态托管**：沙箱里生成+构建，产物落对象存储/本地静态目录，按 slug 路由可玩；不在业务代码里硬编码任何游戏逻辑。
- **可见性**：未发布游戏仅创建者可见（管理员不可见）；发布后管理员统一管理审批/上下架。

## 开发流程

1. 改动前先读相关 `docs/` 与周边代码，确认理解。
2. 多步任务先列计划，每步挂验证点（跑测试/构建/看输出）。
3. 写完代码同步写测试，`uv run pytest` / `pnpm test` 通过。
4. 提交前自检：diff 每行对应一个具体需求；顺手清理自己留下的孤儿导入/变量。
5. Conventional Commits，PR 说明按"目的→背景→改动点→影响→验证结果"。

## 常用命令（落地后）

```bash
# 后端
cd backend && uv sync && uv run pytest && uv run ruff check .
# 前端
cd frontend && pnpm install && pnpm test && pnpm build
# 依赖
docker compose up -d postgres redis worker
```

## 不要做

- 不在业务代码里硬编码任何具体游戏玩法/规则约束——玩法由 Agent 生成。
- 不为不会发生的场景提前抽象、提前兜错。
- 不顺手重构相邻代码；不静默跳过中文字体/IO 阻塞等历史教训点。
