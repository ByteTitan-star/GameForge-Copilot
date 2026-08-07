# 10 · 前后端契约与并行开发

> 本文件是前后端共同的**契约圣经**。两个 agent 各自照此实现，互不等待、互不冲突。
> **规则**：契约即接口，契约先行。任何契约变更必须先改本文件再改代码。

## 1. 并行开发总原则

| 原则 | 说明 |
|---|---|
| 契约先行 | 接口、事件、枚举、错误码先在本文件冻结，双方照写，不靠口头协商 |
| 类型同源 | 后端 Pydantic schema → 导出 OpenAPI → 前端 `openapi-typescript` 生成 TS 类型，单一真相源 |
| 前端 Mock | 前端基于本文件的 schema 先行开发，不依赖后端启动；后端就绪后切真实接口 |
| 边界清晰 | 鉴权/限流/加密/DB/沙箱/计量归后端；UI/路由守卫/状态/类型消费归前端 |
| 不重叠 | 前后端各自目录，共享的只有契约（OpenAPI + 本文件），无代码耦合 |
| 变更流程 | 改契约 → 改本文件 → 双方据 diff 调整 → 类型重新生成 |

## 2. 共享枚举（前后端字面量必须一致）

```ts
// 后端用 Python Enum，前端用 TS const，值必须与下表完全相同
type Role = "user" | "admin";

type GameStatus =
  | "draft"        // 草稿，仅 owner 可见（admin 不可见）
  | "submitted"    // 已提交待审
  | "reviewing"    // 审核中
  | "published"   // 已上架，公开
  | "rejected"     // 已驳回，仅 owner 可见
  | "taken_down";  // 已下架，仅 owner 可见记录

type RunStatus = "running" | "paused" | "done" | "failed";

type RunPhase = "plan" | "art" | "code" | "qa" | "done";

type PublishStatus = "submitted" | "reviewing" | "approved" | "rejected";

type LLMProvider = "anthropic" | "openai" | "openai_compat";

type WSEventType =
  | "phase_start"
  | "llm_call"
  | "tool_call"
  | "build_done"
  | "qa_report"
  | "hitl_wait"
  | "usage"
  | "done"
  | "error";
```

> 状态映射：审批通过后 `publish_request.status=approved` 且 `game.status=published`；驳回 `publish_request.status=rejected` 且 `game.status=rejected`。`game.status` 是对外可见性唯一来源，`publish_request.status` 仅是审批单状态。

## 3. 统一响应格式

### 成功
```json
{ "data": <T> }
```
列表：
```json
{ "data": [<T>], "total": 100, "page": 1, "size": 20 }
```

### 失败
```json
{ "error": { "code": "STRING_CODE", "message": "人类可读说明", "detail": {} } }
```
HTTP 状态码语义化：400 入参错 / 401 未认证 / 403 无权限 / 404 不存在 / 409 状态冲突 / 429 限流 / 500 服务错。

### 错误码表（核心）
| code | HTTP | 含义 |
|---|---|---|
| `UNAUTHORIZED` | 401 | 未登录或 token 失效 |
| `FORBIDDEN` | 403 | 无权限（含 admin 越权查草稿） |
| `EMAIL_NOT_VERIFIED` | 403 | 未验证邮箱，功能受限 |
| `RATE_LIMITED` | 429 | 触发限流 |
| `QUOTA_EXCEEDED` | 429 | token 配额耗尽 |
| `LLM_CONFIG_INVALID` | 400 | LLM 配置无效或连通失败 |
| `GAME_NOT_FOUND` | 404 | 游戏不存在或不可见 |
| `INVALID_STATE` | 409 | 状态机非法转移（如 draft 直接 publish） |
| `SANDBOX_FAILED` | 500 | 沙箱执行失败 |
| `EMAIL_TAKEN` | 409 | 邮箱已注册 |
| `VALIDATION_ERROR` | 400 | 入参校验失败（detail 含字段级错误） |

## 4. 核心端点精确 Schema

> 字段命名 `snake_case`，前后端一致；TS 生成类型也保留 snake_case（OpenAPI 直出，不做 camel 转换，避免对不上）。

### POST /api/v1/auth/register
请求：
```json
{ "email": "a@b.com", "password": "******" }
```
响应 `data`：
```json
{ "user_id": "uuid", "email": "a@b.com", "email_verified": false }
```
错误：`VALIDATION_ERROR`（邮箱格式/密码强度）、`EMAIL_TAKEN`（409）。

### POST /api/v1/auth/login
请求：`{ "email", "password" }`
响应 `data`：
```json
{
  "access_token": "jwt",
  "refresh_token": "opaque",
  "expires_in": 900,
  "user": { "user_id": "uuid", "email": "...", "role": "user", "email_verified": true }
}
```

### POST /api/v1/auth/refresh
请求：`{ "refresh_token": "opaque" }`
响应 `data`：`{ "access_token", "refresh_token", "expires_in" }`（rotation，旧 refresh 失效）

### POST /api/v1/auth/verify-email
请求：`{ "token": "..." }`
响应 `data`：`{ "user_id": "uuid", "email_verified": true }`
错误：`VALIDATION_ERROR`（token 无效/过期）。

### POST /api/v1/auth/password/reset
请求：`{ "email": "a@b.com" }`
响应 `data`：`{ "sent": true }`（无论邮箱是否存在，防枚举）

### POST /api/v1/auth/password/reset/confirm
请求：`{ "token": "...", "new_password": "******" }`
响应 `data`：`{ "user_id": "uuid", "reset": true }`
错误：`VALIDATION_ERROR`（token 无效/过期/已用）。

### POST /api/v1/me/llm-configs
请求：
```json
{ "provider": "anthropic", "model": "claude-...", "apikey": "sk-...", "is_default": true }
```
响应 `data`：
```json
{ "config_id": "uuid", "provider": "anthropic", "model": "claude-...", "apikey_masked": "sk-***...***", "is_default": true, "tested_ok": true }
```
错误：`LLM_CONFIG_INVALID`（连通测试失败，不保存）。

### PATCH /api/v1/me/llm-configs/{config_id}
请求：`{ "model": "...", "is_default": true }`（apikey 不在此改，走重新创建）
响应 `data`：`{ "config_id", "provider", "model", "apikey_masked", "is_default" }`

### DELETE /api/v1/me/llm-configs/{config_id}
响应 `data`：`{ "config_id", "deleted": true }`
错误：`INVALID_STATE`（删除默认配置需先指定新默认）。

### POST /api/v1/me/llm-configs/{config_id}/test
响应 `data`：`{ "config_id", "tested_ok": true, "error": null }`

### POST /api/v1/games
请求：
```json
{ "title": "贪吃蛇", "requirement": "设计一个贪吃蛇，方向键控制，计分..." }
```
响应 `data`：
```json
{ "game_id": "uuid", "owner_id": "uuid", "status": "draft", "current_version": 0, "created_at": "iso8601" }
```

### POST /api/v1/games/{game_id}/runs
请求：
```json
{ "requirement": "本次迭代：加入加速道具", "llm_config_id": "uuid|null" }
```
响应 `data`：
```json
{ "run_id": "uuid", "game_id": "uuid", "status": "running", "phase": "plan", "ws_url": "/ws/runs/uuid" }
```
错误：`QUOTA_EXCEEDED`、`EMAIL_NOT_VERIFIED`、`GAME_NOT_FOUND`、`INVALID_STATE`（game 已发布需新版本）。

### GET /api/v1/games
查询：`?status=draft&page=1&size=20`
响应 `data[]`：
```json
[{ "game_id", "title", "status", "current_version", "slug": "snake-xxx|null", "updated_at" }]
```
可见性：仅返回 `owner_id = me` 的记录，**无论 role**（admin 也只看自己的，除非走审批队列）。

### GET /api/v1/games/public （B2 · 无需登录）
查询：`?page=1&size=20&sort=updated_at|play_count`
响应 `data[]`：
```json
[{
  "game_id": "uuid",
  "title": "贪吃蛇",
  "slug": "snake-abc123",
  "cover_url": null,
  "published_at": "2026-08-07T12:00:00Z",
  "play_count": 42
}]
```
可见性：仅 `status=published`；不含 owner 邮箱等 PII；admin 草稿/审批中游戏不可见。

### GET /api/v1/official-games （Batch A · R1 · 无需登录）
响应 `data[]`：
```json
[{
  "slug": "official-neon-snake",
  "title": "霓虹贪吃蛇",
  "description": "方向键控制，吃豆得分",
  "play_url": "/play/official-neon-snake",
  "thumbnail_url": null
}]
```
可见性：仅系统预置 `status=published` 官方游戏；不含 owner PII。

### POST /api/v1/games/fork/{slug} （Batch A · R1）
- 需 Bearer + 邮箱已验证
- 从官方 published 游戏复制 title（加「（副本）」后缀）、requirement、v1 产物
- 新 game：`status=draft`, `owner=当前用户`, `current_version=1`；不调用 LLM，不 enqueue run
- 响应 `data`：同 `GameResp`
- 错误：`GAME_NOT_FOUND`（非官方 slug）、`QUOTA_EXCEEDED`（草稿上限）

### POST /api/v1/games/{game_id}/versions/{version}/activate （Batch A · R4）
- 需 Bearer + owner
- 校验 `GameVersion` 存在 → 更新 `games.current_version = version`（不删更高版本文件）
- 可选：将该版本 `design_doc` 同步为后续 run 上下文
- 响应 `data`：同 `GameResp`
- 错误：`GAME_NOT_FOUND`、`INVALID_STATE`

### POST /api/v1/runs/{run_id}/retry （Batch A · R3）
- 需 Bearer + owner
- 条件：`status=failed` 或 `status=paused` 且检查点 `phase in (sandbox_failed, qa_failed)`
- 从失败阶段重新 enqueue resume（不清版本号；成功后仍递增新版本）
- 响应 `data`：`{ "run_id", "status": "running", "phase": "code" }`
- 与 `POST /runs/{id}/resume` 区分：resume 用于 HITL/pause；retry 用于失败恢复

### GET /api/v1/me/runs/active （Run 持久化）
- 需 Bearer；返回当前用户所有 `running|paused` 的 run（跨游戏）
- 响应 `data[]`：`{ run_id, game_id, game_title, status, phase, entry_phase, started_at, ws_url }`

### GET /api/v1/runs/{run_id}/events （Run 持久化）
- 需 Bearer + owner；返回 Redis 缓冲的 WS 事件历史（最多 200 条）
- 响应 `data[]`：同 WS `WSEvent` envelope
- WS 连接 `/ws/runs/{run_id}` 握手后会先 replay 缓冲事件，再转发实时流

### GET /api/v1/runs/{run_id} （Run 持久化扩展）
- 响应 `data` 增 `hitl_wait`: `{ node, design_doc, action_url }`（从 Redis 检查点，HITL 态时有值）

### GET /api/v1/templates （Batch B · R2）
- 无需登录；仅 `verified=true` 模板
- 响应 `data[]`：`{ template_id, title, description, tags[], requirement_seed }`

### POST /api/v1/games/{game_id}/runs （Batch B · R5 增 entry_phase）
响应 `data` 增 `entry_phase`: `"plan" | "code"`（智能路由，对用户透明）

### GET /api/v1/runs/{run_id} （Batch B · R5）
响应 `data` 增 `entry_phase`: `"plan" | "code"`

### PATCH /api/v1/me/profile （Batch C · R6）
- 需 Bearer
- 请求：`{ handle?, display_name?, profile_public? }`
- handle 规则：`^[a-z0-9_]{3,32}$`，唯一性冲突 → 409 `HANDLE_TAKEN`
- 响应 `UserProfile`：`{ user_id, email, handle, display_name, profile_public }`

### GET /api/v1/me/profile （Batch C · R6）
- 需 Bearer；响应同上

### GET /api/v1/u/{handle} （Batch C · R6 · 无需登录）
- `profile_public=false` → 404
- 响应 `data`：`{ handle, display_name, total_plays, latest_published_at, games[] }`
- `games[]` 仅 published：`{ game_id, title, slug, play_count, published_at }`

### POST /api/v1/games/{game_id}/like （Batch C · R7）
- 需 Bearer；toggle；仅 published
- 响应：`{ game_id, active, like_count, favorite_count }`

### POST /api/v1/games/{game_id}/favorite （Batch C · R7）
- 同上，收藏 toggle

### GET /api/v1/me/favorites （Batch C · R7）
- 需 Bearer；分页收藏列表

### GET /api/v1/games/featured （Batch C · R7 · 无需登录）
- 按 `featured_rank` 升序；仅 published 且 rank 非空

### GET /api/v1/games/public/{slug} （Batch C · R7）
- 无需登录；公开游戏元数据（含 `like_count`, `favorite_count`, `creator`）

### PATCH /api/v1/admin/games/{game_id}/featured （Batch C · R7 · admin）
- 请求：`{ featured_rank: int | null }`；仅 published；落 audit_logs

### GET /api/v1/games/public （Batch C · 扩展）
- `PublicGameItem` 增 `creator: { handle, display_name }`、`like_count`、`favorite_count`

### GET /api/v1/games/{game_id}
响应 `data`：
```json
{ "game_id", "owner_id", "title", "status", "current_version", "slug", "versions": [{ "version": 1, "artifact_path": "...", "created_at" }], "created_at", "updated_at" }
```
可见性：`status in (draft, rejected, taken_down)` 时仅 owner 可见，否则 404。

### GET /api/v1/games/{game_id}/runs
响应 `data[]`：`[{ "run_id", "status", "phase", "started_at", "ended_at" }]`

### GET /api/v1/games/{game_id}/versions
响应 `data[]`：`[{ "version", "artifact_path", "created_at" }]`

### GET /api/v1/runs/{run_id}
响应 `data`：`{ "run_id", "game_id", "status", "phase", "entry_phase", "ws_url": "/ws/runs/{run_id}", "current_hitl": { "node": "plan_confirm" } | null }`
错误：`GAME_NOT_FOUND`（非 owner 不可见）。

### POST /api/v1/games/{game_id}/take-down （admin）
请求：`{ "reason": "..." }`
响应 `data`：`{ "game_id", "status": "taken_down", "reason": "..." }`
错误：`INVALID_STATE`（非 published 不能下架）。

### POST /api/v1/games/{game_id}/publish/submit
请求：`{ "version": 2, "note": "修复计分" }`
响应 `data`：`{ "publish_request_id": "uuid", "status": "submitted", "game_id", "version": 2 }`
错误：`INVALID_STATE`（仅 draft/rejected/taken_down 可提交发布；published/submitted/reviewing 不可）。

### GET /api/v1/publish/queue （admin）
查询：`?status=submitted`
响应 `data[]`：`[{ "publish_request_id", "game_id", "game_title", "version", "status", "created_at" }]`

### POST /api/v1/publish/{publish_request_id}/approve （admin）
请求：`{}`（无体）
响应 `data`：`{ "publish_request_id", "status": "approved", "game": { "game_id", "slug": "snake-xxx", "status": "published" } }`

### POST /api/v1/publish/{publish_request_id}/reject （admin）
请求：`{ "reason": "..." }`
响应 `data`：`{ "publish_request_id", "status": "rejected", "game": { "game_id", "status": "rejected" } }`

### GET /api/v1/me/usage
响应 `data`：
```json
{
  "today": { "input_tokens": 12345, "output_tokens": 678, "calls": 12 },
  "month": { "input_tokens": ..., "output_tokens": ..., "calls": ... },
  "total":  { "input_tokens": ..., "output_tokens": ..., "calls": ... },
  "quota": { "daily_token_limit": 500000, "daily_used": 13023, "remaining": 486977 }
}
```

### GET /api/v1/admin/usage （admin）
响应 `data`：
```json
{
  "system": { "today": {...}, "month": {...}, "total": {...} },
  "top_users": [{ "user_id", "email", "month_input_tokens": ..., "month_output_tokens": ..., "calls": ... }]
}
```

## 5. WS 事件 Schema

连接：`WS /ws/runs/{run_id}?token=<access_token>`（浏览器原生 WS 不支持自定义头，token 走查询参数），鉴权 owner/admin。access 过期则服务端关闭，前端 refresh 后重连。

每条事件：
```json
{ "type": "<WSEventType>", "run_id": "uuid", "ts": "iso8601", "payload": {...} }
```

### phase_start （Batch A · R3 增人话字段）
```json
{
  "phase": "plan" | "art" | "code" | "qa" | "done",
  "human_label": "正在整理玩法说明",
  "eta_seconds": 120
}
```
`human_label` / `eta_seconds` 由 `app.forge.phase_labels` 静态映射，便于前端阶段卡片展示。

### llm_call
```json
{ "phase": "code", "model": "claude-...", "provider": "anthropic", "input_tokens": 1234, "output_tokens": 567 }
```

### tool_call
```json
{ "phase": "code", "tool": "execute_code", "args": {...}, "status": "ok" | "error", "summary": "构建成功" }
```
art 阶段 `asset_pick` 额外携带 `artifacts: [{ asset_id, filename, kind, data_uri }]`（B9）。

### build_done
```json
{ "version": 3, "artifact_path": "...", "preview_url": "/draft/{game_id}/3" }
```

### qa_report （B1 · 沙箱试玩）
```json
{
  "passed": false,
  "issues": ["pageerror: ReferenceError: x is not defined"],
  "log_excerpt": "playtest: static mode\n...",
  "console_logs": ["console:error:..."],
  "playtest_mode": "sandbox"
}
```
判定来源：`app.sandbox.playtest.run_playtest(index.html)`，非 LLM 自评。失败时在 `qa_max_retries` 内回退 `code` 节点。

### hitl_wait （Batch A · R3 结构化 design_doc）
```json
{
  "node": "plan_confirm",
  "design_doc": {
    "title": "霓虹贪吃蛇",
    "gameplay": "移动、吃豆、计分…",
    "controls": "方向键 / WASD",
    "levels": ["热身", "加速"]
  },
  "action_url": "/api/v1/games/{game_id}/runs/{run_id}/hitl/resolve"
}
```
LLM 输出非 JSON 时 fallback：整段文本放入 `gameplay`，其余字段默认。

### usage
```json
{ "today_used": 13023, "daily_limit": 500000, "remaining": 486977 }
```

### done
```json
{ "run_id": "uuid", "game_id": "uuid", "version": 3, "preview_url": "/draft/{game_id}/3" }
```

### error
```json
{ "code": "SANDBOX_FAILED", "message": "构建超时", "fatal": true }
```

### HITL 解决（HTTP，非 WS）
POST `/api/v1/games/{game_id}/runs/{run_id}/hitl/resolve`
请求：
```json
{ "node": "plan_confirm", "decision": "approve" | "modify", "modify_text": "可选修改意见" }
```
响应 `data`：`{ "run_id", "status": "running", "phase": "art" }`

## 6. 类型同源方案

- 后端 `backend/app/schemas/` 用 Pydantic v2 定义所有请求/响应模型。
- FastAPI 自动生成 OpenAPI（`/openapi.json`）。
- 前端：`pnpm exec openapi-typescript http://localhost:8000/openapi.json -o src/api/types.gen.ts`
- 前端所有 API 调用用生成的类型，禁手写请求/响应类型。
- 共享枚举前端单独维护 `src/api/enums.ts`（值与第 2 节一致），不依赖生成。
- CI 加校验：后端 schema 变更后前端重新生成并 diff，类型不一致则 fail。

## 7. 前端 Mock 策略

- `src/api/` 调用层与实现解耦：接口函数签名固定，实现可切 mock/real。
- `src/api/mock/` 用本文件 schema 写 mock 数据 + MSW（Mock Service Worker）拦截。
- WS mock：`src/ws/mock.ts` 按时间线回放事件序列，模拟生成进度。
- 后端就绪后：环境变量 `VITE_USE_MOCK=false` 切真实；联调按里程碑逐模块切。
- 前端**不阻塞**：契约冻结后即可全量开发，含设计页/管理后台/Setting/试玩页。

## 8. 后端不阻塞前端的保证

- 后端先交付 `/openapi.json`（哪怕路由返回桩数据），前端类型即可生成。
- 后端按里程碑逐步实现真实逻辑，前端按里程碑切 mock→real。
- 任何端点契约变更：先改本文件 → 通知前端 → 前端重新生成类型。

## 9. 并行开发里程碑

> 前后端按同一里程碑推进，每里程碑定义联调点。前置依赖只在本列内。

| # | 里程碑 | 后端交付 | 前端交付 | 联调点 |
|---|---|---|---|---|
| M0 | 契约冻结 | 本文件 + Pydantic schema + `/openapi.json`（桩） | enums.ts + types.gen.ts + mock 全量 | 无（各做各的） |
| M1 | 认证 | register/verify/login/refresh/logout 真实 | 登录/注册/验证页（切 real） | 登录闭环 |
| M2 | LLM 配置 | llm-configs CRUD + 连通测试 + 加密 | Setting 页 LLM 配置（切 real） | 配置闭环 |
| M3 | 用量 | usage 计量写入 + `/me/usage` | Setting 用量看板（切 real） | 用量可见 |
| M4 | 游戏生成骨架 | games CRUD + runs + WS 事件流（plan→code 最小链，可桩） | 设计页 + RunProgress（切 real WS） | 一次 run 端到端 |
| M5 | 沙箱与托管 | sandbox execute_code + hosting + 版本 | 试玩页 GamePlayer（切 real） | 试玩可玩 |
| M6 | 全生成链 | plan/art/code/qa 全子图 + HITL + 检查点 | HitlCard + 断线重连 | 完整生成 |
| M7 | 发布审批 | publish 状态机 + admin 队列 | 管理后台审批工作台 | 审批闭环 |
| M8 | 管理后台余下 | admin 用户/游戏/用量/设置 | 用户管理/游戏管理/系统用量 | 后台闭环 |

## 10. 命名与目录不冲突约定

- 前端 `frontend/`，后端 `backend/`，根目录无共享代码目录。
- 共享只通过本文件 + `openapi.json`，无共享 npm/py 包。
- 字段统一 `snake_case`（见第 4 节）。
- 枚举值统一（见第 2 节）。
- 环境变量：后端不加 `VITE_` 前缀，前端只用 `VITE_` 前缀，互不读取对方变量。

## 11. 不做

- 不在前端硬编码任何后端业务规则（状态转移、可见性判断以 API 返回为准）。
- 不在后端返回前端专用 UI 状态字段（如 `button_disabled`）——前端据 status 自行推导。
- 不绕过契约直传/直读对方数据结构。
- 契约未冻结前不开始 M1+。

## 12. 前后端 Agent 协作流程

> 两个独立 AI agent 共享同一 git 仓库，靠 [contracts/](../contracts/) 目录通信。**不轮询**，靠 git pull 拉变更。

### 目录独占（防 git 冲突）

| 目录 | 写者 | 读者 |
|---|---|---|
| `contracts/` | 后端独占（`INTEGRATION.md` 除外，前端写） | 前端只读 |
| `backend/` | 后端独占 | 前端不碰 |
| `frontend/` | 前端独占 | 后端不碰 |
| `docs/` | 双方（仅契约相关变更才改） | 双方 |

### contracts/ 文件

- `openapi.json` — 唯一接口真相源，后端生成提交
- `CHANGELOG.md` — 后端写的契约变更记录，前端据 diff 定位改哪
- `INTEGRATION.md` — 前端写的端点级 mock→real 状态看板
- `README.md` — 协作规则

### 后端 agent 工作流

1. 改 Pydantic schema / 路由 → `uv run ruff check && uv run pytest`
2. 重新生成快照 `uv run python -m app.export_openapi > contracts/openapi.json`
3. `contracts/CHANGELOG.md` 顶部加一条（ADDED/MODIFIED/REMOVED + 端点 + 影响前端哪块 + 里程碑）
4. 契约变更单独原子 commit

### 前端 agent 工作流

1. 每回合开始 `git pull`，读 `contracts/CHANGELOG.md` 自上次以来的 diff
2. 重新生成类型 `pnpm exec openapi-typescript contracts/openapi.json -o src/api/types.gen.ts`
3. 按 CHANGELOG 影响范围改代码
4. 端点切 mock→real 后更新 `contracts/INTEGRATION.md`
5. commit

### 铁律

- 不轮询文件夹——用 git pull 拉变更。
- 不等后端单测绿才开发——契约定了就据它 mock；真实联调在里程碑联调点（第 9 节）。
- 不手写接口文档——openapi.json 即文档。
- 前端不改 `contracts/`（INTEGRATION.md 除外），后端不改 `frontend/`。
- 契约变更必须先改 openapi.json + CHANGELOG 再改代码，禁止"先改代码后补契约"。

### CI 校验（落地后）

- 后端生成 openapi.json 与仓库快照 diff 不一致 fail（防忘记提交快照）。
- 前端 `types.gen.ts` 与 `contracts/openapi.json` 不一致 fail（防忘记重新生成）。
