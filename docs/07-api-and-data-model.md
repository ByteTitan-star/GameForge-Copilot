# 07 · API 与数据模型

> 端点概览。精确 request/response schema、WS 事件 payload、共享枚举、错误码见 [10-contract-and-parallel-dev.md](10-contract-and-parallel-dev.md)。

## HTTP API（REST）

> 路径前缀 `/api/v1`。鉴权用 `Authorization: Bearer <access_token>`。

### 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/register` | 邮箱+密码注册，触发验证邮件 |
| POST | `/auth/verify-email` | 验证 token 激活 |
| POST | `/auth/login` | 登录，签发 access+refresh |
| POST | `/auth/refresh` | 轮换 refresh |
| POST | `/auth/logout` | 撤销 refresh |
| POST | `/auth/password/reset` | 发重置邮件 |
| POST | `/auth/password/reset/confirm` | 重置确认 |

### LLM 配置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/me/llm-configs` | 列出我的配置（apikey 掩码） |
| POST | `/me/llm-configs` | 新增配置（含连通性测试） |
| PATCH | `/me/llm-configs/{id}` | 改默认/模型 |
| DELETE | `/me/llm-configs/{id}` | 删除 |
| POST | `/me/llm-configs/{id}/test` | 测连通 |

### 游戏生成

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/games` | 建游戏（draft）+ 初始需求，返回 game_id |
| GET | `/games` | 我的游戏列表 |
| GET | `/games/{id}` | 游戏详情（草稿仅 owner） |
| DELETE | `/games/{id}` | 删除草稿 |
| POST | `/games/{id}/runs` | 发起一次生成/迭代 run |
| GET | `/games/{id}/runs` | run 历史 |
| GET | `/games/{id}/versions` | 版本列表 |
| GET | `/runs/{run_id}` | run 当前状态（断线重连用） |

### 发布

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/games/{id}/publish/submit` | 提交发布 |
| GET | `/publish/queue` | 待审队列（admin） |
| POST | `/publish/{id}/approve` | 通过（admin） |
| POST | `/publish/{id}/reject` | 驳回（admin，带理由） |
| POST | `/games/{id}/take-down` | 下架（admin） |

### 试玩与展示

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/play/{slug}` | 已发布游戏入口（公开，静态产物） |
| GET | `/draft/{game_id}/{version}` | 草稿试玩（鉴权 owner） |

### 用量与管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/me/usage` | 我的用量 |
| GET | `/admin/usage` | 系统用量（admin） |
| GET | `/admin/users` | 用户管理（admin） |
| PATCH | `/admin/users/{id}` | 禁用/调角色/配额（admin） |
| GET/PUT | `/admin/settings` | 全局设置（admin） |

## WebSocket

| 路径 | 说明 |
|---|---|
| `/ws/runs/{run_id}` | 订阅某次生成的实时事件流（鉴权） |

事件类型：`phase_start` / `llm_call` / `tool_call` / `hitl_wait` / `build_done` / `qa_report` / `done` / `error`。

## PostgreSQL 表结构

```sql
users(
  id uuid pk,
  email text unique not null,
  password_hash text not null,
  role text not null default 'user',  -- user/admin
  email_verified bool not null default false,
  disabled bool not null default false,
  created_at timestamptz
)

user_llm_config(
  id uuid pk,
  user_id uuid fk users,
  provider text not null,          -- anthropic/openai/...
  model text not null,
  apikey_enc bytea not null,        -- 加密
  is_default bool default false,
  created_at timestamptz
)

games(
  id uuid pk,
  owner_id uuid fk users,
  slug text unique,                 -- published 后才有
  title text not null,
  status text not null,             -- draft/submitted/reviewing/published/rejected/taken_down
  current_version int,
  created_at, updated_at timestamptz
)

game_versions(
  id uuid pk,
  game_id uuid fk games,
  version int not null,
  artifact_path text not null,      -- 托管路径
  design_doc jsonb,
  created_at timestamptz
)

generation_runs(
  id uuid pk,
  game_id uuid fk games,
  user_id uuid fk users,
  llm_config_id uuid fk user_llm_config,
  requirement text not null,
  status text not null,             -- running/paused/done/failed
  phase text,                       -- plan/art/code/qa/done
  checkpoint_ref text,              -- Redis 检查点 key
  started_at, ended_at timestamptz
)

publish_requests(
  id uuid pk,
  game_id uuid fk games,
  version int not null,
  status text not null,             -- submitted/reviewing/approved/rejected
  reviewer_id uuid fk users,
  reject_reason text,
  created_at, reviewed_at timestamptz
)

audit_logs(
  id uuid pk,
  actor_id uuid fk users,
  action text not null,             -- approve/reject/take_down/disable_user/...
  target text,
  detail jsonb,
  created_at timestamptz
)

email_verification(
  token text pk,
  user_id uuid fk users,
  expires_at timestamptz
)

password_reset_tokens(
  token text pk,
  user_id uuid fk users,
  expires_at timestamptz,
  used bool default false
)

system_settings(
  key text pk,
  value jsonb not null,
  updated_by uuid fk users,
  updated_at timestamptz
)

-- trace 不落库，统一上报 langfuse Cloud（见 09-deployment.md）
```

## Redis Key 设计

| Key 模式 | 类型 | 用途 |
|---|---|---|
| `usage:user:{uid}:day:{date}` | hash | 用户日用量 |
| `usage:user:{uid}:month:{ym}` | hash | 用户月用量 |
| `usage:user:{uid}:total` | hash | 用户累计 |
| `usage:sys:day:{date}` / `:month:{ym}` / `:total` | hash | 系统用量 |
| `rl:user:{uid}:llm` | zset/counter | LLM 调用限流 |
| `rl:login:{ip}` | counter | 登录限流 |
| `rl:register:{ip}` | counter | 注册限流 |
| `refresh:{token}` | string | refresh token 白名单，TTL |
| `run:ckpt:{run_id}` | string | LangGraph 检查点 |
| `run:ws:{run_id}` | pubsub | run 事件广播 |
| `quota:user:{uid}` | hash | 用户配额覆盖值 |

## 响应约定

- 成功：`{"data": ...}`。
- 失败：`{"error": {"code": "...", "message": "..."}}`，HTTP 状态码语义化。
- 列表带分页：`?page&size`，返回 `{data, total, page, size}`。
