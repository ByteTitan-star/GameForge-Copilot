# GameForge 代码库学习导读

> 面向初学者的**系统阅读地图**：每个目录做什么、每个文件干什么、先看什么后看什么、重点函数在哪。
> 配合 `backend/app` 内函数级中文 docstring 一起使用。

---

## 0. 30 秒认知

**GameForge** = 前端 Forge 工作台 + 后端 FastAPI + RabbitMQ Worker + LangGraph 生成流水线。

主链路一句话：

```text
用户输入玩法 → POST /games → POST /games/{id}/runs → Worker 跑 graph.py
→ Plan → HITL → Art → CodeQaLoop(playtest) → promote 版本 → /draft 试玩
```

---

## 1. 推荐阅读顺序（7 阶段）

| 阶段 | 目标 | 读什么 | 验证方式 |
|------|------|--------|----------|
| **1** | 跑通本地 | `README_zh.md` → `docs/development.zh-CN.md` → `docker-compose.yml` | 前后端能登录、打开 Forge |
| **2** | HTTP 入口 | `backend/app/main.py` → `api/*.py` → `schemas/*.py` | Swagger `/docs` 对照路由 |
| **3** | 数据模型 | `models/*.py` → `enums.py` | 画出 Game / GenerationRun / GameVersion 关系 |
| **4** | 发起 Run | `games/services.py` → `messaging/*` → `forge/runner.py` | 打断点看 `create_run` |
| **5** | 生成核心 | `forge/graph.py` → `forge/code_qa_exec.py` → `sandbox/playtest.py` | 跟一次完整 WS 事件 |
| **6** | 前端联动 | `ForgePage.tsx` → `forge-events.ts` → `ws/client.ts` | 浏览器 Network + WS |
| **7** | 横切能力 | `llm/*` `guard.py` `memory/*` `hosting/*` `docs/adr/` | 按需深入 |

**不要一上来读 `forge/graph.py`（近 2000 行）**——先完成阶段 2–4，再读它。

---

## 2. 仓库顶层目录

| 目录/文件 | 作用 |
|-----------|------|
| `backend/` | Python 后端：API、ORM、Forge、Worker、沙箱 |
| `frontend/` | React + Vite 前端 |
| `contracts/` | OpenAPI 契约快照（`openapi.json` 为真相源） |
| `docs/` | ADR、开发文档、评测报告、**本导读** |
| `eval/` | 离线评测 runner + 数据集 |
| `docker/` | 各服务 Dockerfile |
| `scripts/` | 种子数据、运维、验证脚本 |
| `data/` `logs/` `tmp/` | 本地运行时目录 |
| `change/` | 本地部署包（已 gitignore，不入库） |
| `.github/` | CI（pytest、eval gate） |
| `CLAUDE.md` | 编码规范与 Git 工作流 |

---

## 3. `backend/app/` 总览

```text
backend/app/
├── main.py          # FastAPI 装配入口
├── enums.py         # 全局枚举（RunPhase/RunStatus/...）
├── api/             # HTTP 路由（薄层）
├── schemas/         # Pydantic 请求/响应（契约源头）
├── models/          # SQLAlchemy ORM
├── games/           # 游戏 & Run 业务逻辑
├── forge/           # ★ AI 生成流水线（最大模块）
├── llm/             # LLM 调用、熔断、embedding
├── messaging/       # RabbitMQ + Outbox + Worker
├── sandbox/         # 构建 & Playwright 试玩
├── hosting/         # 产物存储 & /draft /play 静态路由
├── auth/            # 注册登录 OAuth JWT
├── ws/              # Run 进度 WebSocket
├── usage/           # Token 配额计费
├── admin/ publish/ feedback/ ...  # 周边业务
└── core/            # 配置、DB、错误、日志、指标
```

---

## 4. `backend/app` 逐目录文件说明

### 4.1 根文件

| 文件 | 职责 | 重点看 |
|------|------|--------|
| `main.py` | 创建 FastAPI app、注册路由、CORS、lifespan | `lifespan`, `app.include_router` |
| `enums.py` | 全站枚举：`RunPhase` plan/art/code/qa/done；`RunStatus`；`EntryPhase` | `RunPhase`, `RunCommandType`, `EntryPhase` |
| `export_openapi.py` | 导出 `contracts/openapi.json` | `export()` |

### 4.2 `core/` — 基础设施

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `config.py` | `Settings`：环境变量、Forge/LLM/Memory 开关 | `settings` 单例 |
| `db.py` | 异步 SQLAlchemy Session | `SessionLocal`, `get_db` |
| `redis.py` | Redis 连接 | `get_redis` |
| `errors.py` | `AppError` + 全局异常处理 | `ErrorCode`, `register_exception_handlers` |
| `response.py` | 统一 JSON 包装 `{data, error}` | `SuccessResponse`, `ErrorResponse` |
| `logging.py` | 结构化日志 | `setup_logging` |
| `metrics.py` | Prometheus 指标 | `register_metrics` |
| `langfuse.py` | LLM trace 可观测 | `init_langfuse`, `flush_langfuse` |
| `cdn_policy.py` | 游戏 HTML 允许加载的 CDN 白名单 | `ALLOWED_CDN_HOSTS` |
| `security_boot.py` | 生产环境密钥检查 | `assert_production_secrets` |

### 4.3 `schemas/` — API 契约（无业务逻辑）

Pydantic 模型，被 `api/` 引用。**改字段后必须重跑 `export_openapi`。**

| 文件 | 对应领域 | 关键模型 |
|------|----------|----------|
| `game.py` | 游戏 CRUD | `GameCreate`, `GameResp`, `GameDetailResp` |
| `run.py` | Run 生命周期 | `RunCreate`（requirement 上限）, `HitlResolveReq` |
| `auth.py` | 认证 | `RegisterReq`, `LoginReq` |
| `forge_message.py` | Forge 对话历史 | `ForgeMessageItem` |
| `llm_config.py` | 用户 LLM 配置 | `LLMConfigCreate` |
| `admin.py` | 管理后台 | `AdminSettings` |
| `publish.py` | 发布审核 | `PublishSubmitReq` |
| 其余 | profile/usage/feedback/ws... | 见文件名 |

### 4.4 `models/` — 数据库表

| 文件 | 表 | 关键字段 |
|------|-----|----------|
| `game.py` | `games` | `title`, `requirement`, `status`, `current_version`, `session_summary_json` |
| `generation_run.py` | `generation_runs` | `requirement`, `phase`, `status`, `entry_phase` |
| `game_version.py` | `game_versions` | `artifact_path`, `design_doc`, `thumbnail_path` |
| `forge_message.py` | `forge_messages` | 对话持久化（Memory 数据源） |
| `run_checkpoint.py` | `run_checkpoints` | LangGraph 检查点 |
| `run_command.py` | `run_commands` | HITL 命令幂等 |
| `user.py` | `users` | 账号 |
| `llm_config.py` | `user_llm_configs` | 用户自带 API Key |
| `artifact_revision.py` | 产物版本谱系 | Plan/Art/Candidate revision |
| `failure_report.py` | 失败报告 | QA 失败详情 |
| `task_outbox.py` | Outbox 任务 | 可靠消息投递 |

**关系核心**：`User` 1—N `Game` 1—N `GenerationRun`；`Game` 1—N `GameVersion`。

### 4.5 `api/` — HTTP 路由（薄层，逻辑在 services）

| 文件 | 路由前缀 | 职责 | 重点端点 |
|------|----------|------|----------|
| `games.py` | `/games` | 游戏 CRUD、版本、预览 token | `create_game`, `list_games`, `get_preview_token` |
| `runs.py` | `/games/{id}/runs`, `/runs/{id}` | 发起/查询/控制 Run、HITL | `create_run`, `resolve_hitl`, `get_run_status` |
| `auth.py` | `/auth` | 注册登录验证 | `register`, `login`, `verify_email` |
| `templates.py` | `/templates` | 游戏模板列表 | `list_templates` |
| `publish.py` | `/publish` | 提交发布 | `submit_publish` |
| `admin.py` | `/admin` | 管理后台 | 用户/审核/设置 |
| `health.py` | `/health` | 健康检查 | `health` |
| `llm_config.py` | `/llm-configs` | 用户 LLM 配置 | CRUD |
| `preferences.py` | `/me/preferences` | 用户偏好 | GET/PATCH |
| `usage.py` | `/usage` | 用量统计 | |
| `dev.py` | `/dev` | 开发专用（需开关） | flush/requeue |
| 其余 | favorites/feedback/official/profile/... | 社交与周边 | |

### 4.6 `games/` — 游戏业务

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `services.py` | **游戏与 Run 的 CRUD 核心** | `create_game`, `create_run`, `list_runs`, `retry_run`, `cancel_run` |
| `official.py` | 官方示例游戏 seed | `seed_official_games` |

`create_run` 流程：校验邮箱/配额/LLM 配置 → `classify_entry_phase` → 写 `GenerationRun` → `add_message` → Outbox 投递 `TASK_EXECUTE_RUN`。

### 4.7 `messaging/` — 异步任务

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `outbox.py` | 事务性发任务 | `add_task`, `cancel_run_tasks` |
| `tasks.py` | 任务类型常量 | `TASK_EXECUTE_RUN` |
| `worker.py` | RabbitMQ 消费循环 | `run_worker` |
| `handlers.py` | 任务分发 | `dispatch_task` → `execute_run` / `resume_run` |
| `rabbit.py` | 连接与队列声明 | |
| `memory.py` | 测试用内存队列 | |

### 4.8 `forge/` — ★ 生成流水线（重点）

#### 编排层

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `graph.py` | **LangGraph 主图**：Plan→Art→CodeQa→Done | `run_generation`, `_build_graph`, `plan_node`, `code_qa_loop_node`, `route_start`, `_compose_plan_input` |
| `runner.py` | Worker 入口：租约锁 + 调 graph | `execute_run`, `resume_run` |
| `code_qa_exec.py` | 代码生成/修复 + playtest 编排 | `execute_code_or_repair`, `execute_playtest`, `execute_diagnose` |
| `queue.py` | HITL 恢复入队 | `enqueue_resume` |
| `hitl.py` | HITL 阶段判断与允许命令 | `is_hitl_phase`, `allowed_commands_for` |
| `control.py` | Run 暂停/取消控制面 | `pause_run`, `cancel_run` |
| `state.py` | Redis 检查点读写 | `save_state`, `load_state`, `clear_state` |
| `commands.py` | Run 命令规范化 | `normalize_resume_command` |
| `runner.py` | 执行入口 | |

#### 策划 & 美术

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `design_doc.py` | 策划稿 JSON 解析/校验 | `parse_design_doc`, `validate_design_doc`, `design_doc_to_text` |
| `prompts.py` | 各阶段 system prompt | `PLAN_PROMPT`, `build_code_prompt`, `build_art_options_prompt_async` |
| `art_direction.py` | 美术方向 JSON 解析 | `parse_art_options`, `parse_art_detail` |
| `entry_router.py` | 迭代入口路由 plan/code/chat | `classify_entry_phase` |
| `engine_router.py` | 引擎选择 canvas/phaser3/pixijs | `normalize_engine_id` |

#### 记忆（多轮对话）

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `memory/context_builder.py` | **拼 prompt + token 预算裁剪** | `ContextBuilder.build`, `estimate_tokens` |
| `memory/loader.py` | 从 DB 装配 Memory | `build_node_context` |
| `memory/summary.py` | Session 摘要 schema + 确定性压缩 | `synthesize_summary_from_turns`, `should_refresh_summary` |
| `memory/llm_summary.py` | LLM 摘要（可选） | `synthesize_summary_via_llm` |
| `memory/refresh.py` | 刷新摘要写回 DB | `refresh_session_summary_if_needed` |
| `memory/preferences.py` | 用户偏好读写 | `list_active_preferences`, `upsert_preferences_from_text` |

#### 安全 & 质量

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `guard.py` | 流式 LLM + 输入输出审核 | `run_streamed_llm`, `quick_filter` |
| `llm_continuation.py` | 代码输出截断续写 | `generate_code_output` |
| `subgraphs/code_qa_loop.py` | Code↔Playtest↔Diagnose 子图 | `build_code_qa_loop` |
| `qa/diagnose.py` | QA 失败根因分析 prompt | |
| `reliability/*` | 超时重试、幂等、产物门禁 | `derive_artifact_gate` |
| `lineage.py` | 产物 revision 谱系 | `promote_revision` |

#### 构建

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `build/pipeline.py` | Vite 多文件构建 | `run_build_pipeline` |
| `build/integration.py` | 构建错误反馈 LLM | |
| `build/routing.py` | 依赖路由决策 | `coerce_build_routing` |
| `build/code_output.py` | 解析 LLM 代码输出 | `parse_llm_code_output` |
| `code_candidate.py` | 候选版本写入 & promote | `commit_candidate`, `promote_candidate` |

#### 其他 forge 文件

| 文件 | 一句话 |
|------|--------|
| `messages.py` | Forge 对话消息持久化 `add_message` |
| `events.py` | WS 事件发布 `publish_event` |
| `event_log.py` | 事件日志查询 |
| `failure.py` | 失败报告生成 |
| `capability.py` | 能力不匹配检测 |
| `cache/*` | Redis 模板缓存、语义缓存 |
| `skills/*` | Agent 技能目录与路由 |
| `lexicon/*` | 敏感词匹配 |
| `templates/loader.py` | 内置游戏模板 |
| `assets/picker.py` | 内置素材选取 |
| `tracing.py` | Langfuse 子系统 trace |
| `phase_labels.py` | 阶段中文标签 |
| `adr_evidence.py` | ADR 证据核验 |

### 4.9 `llm/` — 模型调用

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `client.py` | **统一 LLM 入口**：配额、熔断、记账 | `call_llm`, `call_llm_stream` |
| `provider.py` | OpenAI 兼容协议实现 | `complete`, `complete_stream` |
| `circuit.py` | 按 user+provider 熔断 | |
| `services.py` | LLM 配置 CRUD | |
| `embeddings.py` | 向量 embedding | |
| `url_safety.py` | base_url 安全校验 | |

### 4.10 `sandbox/` — 构建与试玩

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `playtest.py` | **Playwright 无头试玩**（QA 门禁） | `run_playtest`, `_session_playtest` |
| `builder.py` | Docker 沙箱构建 | |
| `local.py` | 本地构建（dev） | |
| `lifecycle.py` | 容器生命周期 | |
| `tiers.py` | 沙箱等级 local/docker/daytona | |
| `motion.py` | 画面运动信号检测 | |

### 4.11 `hosting/` — 产物托管

| 文件 | 职责 | 重点函数 |
|------|------|----------|
| `store.py` | 产物目录读写 | `index_path`, `write_version` |
| `routes.py` | `/draft/{game}/{ver}/`, `/play/{slug}/` | |
| `preview_token.py` | 预览 JWT | `mint_preview_token` |
| `local.py` / `s3.py` | 存储后端 | |

### 4.12 `auth/` `usage/` `ws/` 等周边

| 目录 | 职责 | 入口文件 |
|------|------|----------|
| `auth/` | JWT、OAuth、注册验证 | `services.py`, `deps.py`（`get_current_user`） |
| `usage/` | Token 配额 | `quota.py`, `store.py` |
| `ws/runs.py` | Run WS | `ws_run_events` |
| `admin/services.py` | 管理后台逻辑 | |
| `publish/services.py` | 发布审核 | |
| `feedback/services.py` | 用户反馈邮件 | |
| `notify/services.py` | 站内通知 | |
| `email/` | 邮件队列 worker | |
| `dev/runtime.py` | 开发环境 Redis 清理 | |
| `scheduler/services.py` | 定时扫描 stale run | |

---

## 5. `frontend/src/` 导读

### 5.1 阅读顺序

1. `main.tsx` → `App.tsx` → `routes.tsx`
2. `api/client.ts` + `api/games.ts` + `api/enums.ts`
3. `pages/forge/ForgePage.tsx`（核心页面）
4. `pages/forge/forge-events.ts`（WS 事件处理）
5. `ws/client.ts`
6. `components/forge/*`（UI 组件）
7. `components/game/GamePlayer.tsx`（试玩 iframe）

### 5.2 目录速查

| 目录 | 文件数 | 职责 |
|------|--------|------|
| `pages/forge/` | 8 | Forge 页：编排、恢复、事件桥接 |
| `components/forge/` | 29 | 输入框、HITL 卡片、阶段管线、代码预览 |
| `api/` | 29 | REST 封装 + `types.gen.ts`（OpenAPI 生成） |
| `stores/` | 7 | Zustand：auth、theme、toast |
| `lib/` | 34 | hosting URL、HITL 命令、主题工具 |
| `i18n/` | 3 | 中英文文案 `messages.ts` |
| `pages/admin/` | 9 | 管理后台 |
| `pages/auth/` | 5 | 登录注册 |
| `pages/play/` | 4 | 公开试玩页 |

### 5.3 关键前端文件

| 文件 | 职责 | 重点 |
|------|------|------|
| `ForgePage.tsx` | Forge 主页面 | `startGeneration`, `onSend`, `handleForgeWsEvent` |
| `ForgeComposer.tsx` | 需求输入框 | `maxLength=10000` |
| `HitlCard.tsx` | 策划/美术确认 UI | approve/modify |
| `forge-events.ts` | WS 事件 → UI 状态 | `PHASE_START`, `HITL_WAIT`, `DONE` |
| `StagePipeline.tsx` | 四阶段进度条 | |
| `GamePlayer.tsx` | iframe 试玩 | |
| `api/games.ts` | `create`, `startRun`, `resolveHitl` | |

---

## 6. `contracts/` `eval/` `docker/`

| 路径 | 作用 |
|------|------|
| `contracts/openapi.json` | API 契约快照；改 schema 后 `uv run python -m app.export_openapi` |
| `contracts/README.md` | 前后端协作规则 |
| `eval/runners/` | 各维度评测（generation/security/reliability） |
| `eval/datasets/` | 评测 JSON 数据集 |
| `eval/run_all.py` | 一键跑评测 |
| `docker/` | backend/worker/sandbox Dockerfile |

---

## 7. 主链路文件索引（创建游戏 → 完成）

```text
ForgePage.onSend
  → api/games.ts:startRun
    → api/runs.py POST /games/{id}/runs
      → games/services.py:create_run
        → forge/messages.py:add_message
        → messaging/outbox.py:add_task(TASK_EXECUTE_RUN)
          → messaging/worker.py
            → messaging/handlers.py:dispatch_task
              → forge/runner.py:execute_run
                → forge/graph.py:run_generation
                  → plan_node → HITL → art_options_node → art_detail_node
                  → code_qa_loop_node
                    → forge/code_qa_exec.py
                    → sandbox/playtest.py
                  → done_node → promote
  ← ws/runs.py ← forge/events.py:publish_event
  ← forge-events.ts ← ForgePage 更新 UI
  → hosting/routes.py:/draft/{id}/{ver}/
  → GamePlayer.tsx 试玩
```

---

## 8. Forge 四阶段在代码中的对应

| 阶段 | `RunPhase` | graph 节点 | LLM kind | 输出 |
|------|------------|------------|----------|------|
| 策划 | `plan` | `plan_node`, `revise_plan_node` | plan | `design_doc` JSON |
| 美术 | `art` | `art_options_node`, `art_detail_node` | art | `art_direction` |
| 开发 | `code` | `code_qa_loop` → `execute_code_or_repair` | code/repair | HTML/工程文件 |
| 测试 | `qa` | `execute_playtest`, `execute_diagnose` | diagnose | `qa_ok` 布尔 |

迭代时 `entry_router.classify_entry_phase` 可跳过 Plan，直达 `code_qa_loop`。

---

## 9. 配置项速查（`core/config.py`）

| 配置 | 默认 | 影响 |
|------|------|------|
| `memory_context_budget_tokens` | 4000 | Memory 注入 prompt 总预算 |
| `memory_session_summary` | true | 是否启用 Session 摘要 |
| `memory_session_summary_llm` | true | 摘要是否走 LLM |
| `code_qa_max_attempts` | 3 | Code/QA 最大重试 |
| `llm_max_tokens` | 8192 | Plan/Art 输出上限 |
| `llm_code_max_tokens` | 32768 | Code 输出上限 |
| `forge_run_max_tokens` | 500000 | 单次 Run 累计 token 上限 |

---

## 10. `backend/app` 中文函数注释进度

> 目标：`backend/app` 全部 **1103** 个函数添加中文 docstring（作用 / 场景 / 入参 / 返回值）。
> 格式见 `forge/memory/summary.py`、`forge/memory/context_builder.py`。

| 模块 | 状态 |
|------|------|
| `core/` | ✅ 已完成 |
| `main.py`, `enums.py`, `export_openapi.py` | ✅ 已完成 |
| `forge/`（含 `graph.py` 嵌套节点、`build/`、`skills/`、`cache/`、`reliability/`） | ✅ 已完成 |
| `llm/` | ✅ 已完成 |
| `api/`, `games/`, `auth/` | ✅ 已完成 |
| `sandbox/`, `hosting/` | ✅ 已完成 |
| `messaging/`, `ws/`, `dev/`, `scheduler/` | ✅ 已完成 |
| `usage/`, `analytics/`, `schemas/profile.py` 等外围 | ✅ 已完成 |
| `models/` | ✅ 全部 ORM 类已加中文类注释 |
| `schemas/` | ✅ 全部 Pydantic 类已加中文类注释 |

**当前进度（2026-08-23）**：

- `backend/app` 全部 **函数** 中文 docstring：AST 扫描 0 遗漏
- `models/` + `schemas/` 全部 **类** 中文 docstring：已完成
- `py_compile` 语法检查通过

---

## 11. 调试建议

1. **看 Run 卡在哪**：`GET /api/v1/runs/{id}` → `phase` + `hitl_wait`
2. **看事件流**：`GET /api/v1/runs/{id}/events` 或浏览器 WS
3. **看对话历史**：`GET /api/v1/games/{id}/messages`
4. **看产物**：`.hosting/{game_id}/{version}/index.html`
5. **关 Memory 对比质量**：`.env` 设 `MEMORY_CONTEXT_BUILDER=false` 做 A/B

---

最后更新：2026-08-23
