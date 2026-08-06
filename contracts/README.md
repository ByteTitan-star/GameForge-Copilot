# contracts/ — 前后端契约与协作目录

> 两个独立 AI agent 共享同一 git 仓库，靠本目录通信。**不轮询**，靠 git pull 拉变更。

## 文件

| 文件 | 谁写 | 用途 |
|---|---|---|
| `openapi.json` | 后端生成、提交 | 唯一接口真相源（Pydantic schema → FastAPI 自动出） |
| `CHANGELOG.md` | 后端写 | 每次契约变更的结构化记录，前端据 diff 定位改哪 |
| `INTEGRATION.md` | 前端写 | 端点级联调状态（mock→real），后端据此知联调进度 |
| `README.md` | 双方 | 本文件，协作规则 |

## 目录独占（防 git 冲突）

| 目录 | 写者 | 读者 |
|---|---|---|
| `contracts/` | **后端独占**（INTEGRATION.md 除外，前端写） | 前端只读 |
| `backend/` | 后端独占 | 前端不碰 |
| `frontend/` | 前端独占 | 后端不碰 |
| `docs/` | 双方（仅契约相关变更才改） | 双方 |

## 后端 agent 工作流

1. 改 Pydantic schema / 路由 → `uv run ruff check && uv run pytest`
2. 重新生成快照：`uv run python -m app.export_openapi > contracts/openapi.json`
3. 在 `contracts/CHANGELOG.md` 顶部加一条（ADDED/MODIFIED/REMOVED + 端点 + 影响前端哪块 + 里程碑）
4. commit（契约变更单独原子提交）
5. 前端经 git pull 看到变更

## 前端 agent 工作流

1. 每回合开始 `git pull`，读 `contracts/CHANGELOG.md` 自上次以来的 diff
2. 重新生成类型：`pnpm exec openapi-typescript contracts/openapi.json -o src/api/types.gen.ts`
3. 按 CHANGELOG 影响范围改前端代码
4. 端点切 mock→real 后，更新 `contracts/INTEGRATION.md` 状态
5. commit

## 铁律

- **不轮询**文件夹——用 git pull 拉变更。
- **不等后端单测绿才开发**——契约（openapi.json）定了就据它 mock 开发；真实联调在里程碑联调点（见 docs/10 第 9 节）。
- **不手写接口文档**——openapi.json 即文档，手写必漂移。
- 前端不改 `contracts/`（INTEGRATION.md 除外，只读）；后端不改 `frontend/`。
- 任何契约变更必须先改 openapi.json + CHANGELOG，再改代码——禁止"先改代码后补契约"。

## CI 校验（落地后）

- 后端启动生成的 openapi.json 与仓库 `contracts/openapi.json` 快照 diff，不一致 fail（防忘记提交快照）。
- 前端 `types.gen.ts` 与 `contracts/openapi.json` 不一致 fail（防忘记重新生成）。
