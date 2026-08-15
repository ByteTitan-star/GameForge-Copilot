# 契约变更日志

> 后端 agent 每次改接口后在此顶部加一条。前端 agent `git pull` 后读 diff 定位改动。
> 格式：`- <TYPE>: <METHOD> <path> — <说明> (M<x>)`
> TYPE ∈ `ADDED` / `MODIFIED` / `REMOVED` / `DEPRECATED`

---

- ADDED: `POST /api/v1/games/{game_id}/versions/{version}/preview-token` — owner 签发 draft 多文件 preview token（§19.2），返回 `preview_url` + `expires_in_s`；Vite dist 试玩 iframe 用 token 路径加载 assets。
- ADDED: `GET /preview/{token}/{game_id}/{version}/` 及 `/{path}` — draft 多文件产物 token 鉴权试玩（hosting 根路由，非 `/api/v1`）。
- ADDED: `PreviewTokenResp` schema — `preview_url`、`expires_in_s`。

- ADDED: `GET /games/{game_id}/messages` — 按游戏读取持久化的 Forge 用户可见对话历史，支持 `limit` / `before` 游标分页。

- ADDED: `GET /games/{game_id}/versions/{version}/download` — 仅游戏所有者可下载指定版本的独立 HTML 附件；版本、产物缺失或非所有者均返回 404，前端以 Bearer 请求后保存 Blob。

- ADDED: `GET /play/{slug}/thumb.png` — 已发布游戏的生成时截图封面（公开，不触发 PV 统计）。
- MODIFIED: `GameListItem` 增 `cover_url`（仅 published 指向 `/play/{slug}/thumb.png`；草稿不拼——`<img>` 带不了 Bearer 会 401，回退渐变即可）；`VersionItem` 增 `thumbnail_path`；`PublicGameMeta.cover_url` 由硬编码 None 改为按 `cover_path` 填充。

## 未发布（working copy）

- MODIFIED: `GET /games/public`、`GET /games/featured`、`GET /official/games` — 增 `locale` query（zh | en，官方样例标题随 locale 切换）
- MODIFIED: `GET /play/{slug}/` — 增 `locale` query（en 时优先返回英文静态页）
- MODIFIED: `PublicGameMeta` — 增 `featured: bool`（由 `featured_rank` 推导）

- ADDED: Run 事件 Redis 缓冲 + WS 连接时 replay；`GET /runs/{id}/events` HTTP 回退
- ADDED: `GET /me/runs/active` — 跨游戏进行中的 run 列表（刷新/跳转后找回）
- MODIFIED: `GET /runs/{id}` — 增 `hitl_wait`（从 Redis 检查点恢复完整 design_doc）

<!-- 后端改契约后在此追加，commit 时归入下一条日期标题 -->

- MODIFIED: `GET /templates` — 仅返回 verified 模板；catalog 含 reference_artifact CI playtest (Batch B · B-B1)
- MODIFIED: `POST /games/{id}/runs`、`GET /runs/{id}` — 响应增 `entry_phase: plan|code` 智能路由 (Batch B · R5)
- ADDED: `GET/PATCH /me/profile` — handle/display_name/profile_public (Batch C · R6)
- ADDED: `GET /u/{handle}` — 公开创作者主页 (Batch C · R6)
- ADDED: `POST /games/{id}/like|favorite` — toggle 点赞/收藏 (Batch C · R7)
- ADDED: `GET /me/favorites` — 我的收藏列表 (Batch C · R7)
- ADDED: `GET /games/featured` — 本周精选 (Batch C · R7)
- ADDED: `GET /games/public/{slug}` — 公开游戏元数据含 creator/计数 (Batch C · R7)
- MODIFIED: `GET /games/public` — 增 creator、like_count、favorite_count (Batch C · R7)
- ADDED: `PATCH /admin/games/{id}/featured` — 管理员设精选 rank + 审计 (Batch C · R7)
- ADDED: 错误码 `HANDLE_TAKEN`(409)
- ADDED: `GET /official-games` — 官方预置游戏列表（无需登录）；`OfficialGameItem` (Batch A · R1)
- ADDED: `POST /games/fork/{slug}` — Fork 官方游戏为当前用户 draft，复制 v1 产物 (Batch A · R1)
- MODIFIED: WS `phase_start` — 新增 `human_label`、`eta_seconds` (Batch A · R3)
- MODIFIED: WS `hitl_wait.design_doc` — 结构化 JSON + 纯文本 fallback (Batch A · R3)
- ADDED: `POST /runs/{run_id}/retry` — 失败阶段重试（sandbox_failed/qa_failed）(Batch A · R3)
- ADDED: `POST /games/{game_id}/versions/{version}/activate` — 版本回滚切换 current_version (Batch A · R4)
- ADDED: `GET /me/usage/breakdown?scope=game|run` — 按游戏/Run 维度用量明细 + 估算 USD (B3)
- ADDED: `GET /games/{game_id}/usage` — 单游戏当月用量汇总 (B3)
- ADDED: `GET /games/{game_id}/analytics` — PV/UV + play_count (B4)
- ADDED: `GET /admin/analytics/top` — 管理员 Top 游戏 PV 排行 (B4)
- ADDED: `GET /templates` — 内置模板目录；`POST /games` 可选 `template_id` 预填 title/requirement (B5)
- MODIFIED: 产物托管 — `HOSTING_BACKEND=local|s3`，S3 写远端 + 本地缓存 (B6)
- ADDED: `GET /oauth/{provider}/start|callback` — GitHub/Google OAuth 登录/绑定 (B7)
- ADDED: `PATCH /admin/games/{game_id}/schedule` — 设置 `scheduled_take_down_at` / `scheduled_publish_at`；worker 每 60s 扫描到期下架 (B8)
- ADDED: `GET /games/public` — 公开已发布游戏发现（无需登录）；`PublicGameItem` 含 `game_id, title, slug, cover_url, published_at, play_count`；无 owner PII (B2)
- MODIFIED: `qa_report` WS payload — 新增 `console_logs[]`、`playtest_mode`；QA 由沙箱试玩驱动非 LLM 自评 (B1)
- MODIFIED: `tool_call` art 阶段 — `asset_pick` 返回 `artifacts[]` 清单 (B9)
- MODIFIED: `AdminSettings` — 新增 `admin_contact_email`；禁用账号登录提示联系邮箱
- ADDED: `DELETE /admin/users/{id}` — 管理员删除用户
- ADDED: `POST /runs/{id}/pause|resume|cancel` — 长任务中断/续跑/取消；HITL 后 run.status=`paused` (docs/01)
- ADDED: `GET /me/notifications`、`POST /me/notifications/{id}/read` — 站内通知收件箱 (docs/04)
- ADDED: `GET /admin/audit-logs` — 管理员操作审计分页 (docs/01 §8)
- ADDED: `GET /admin/games` — 管理员已发布/审批中游戏列表（不含草稿）(docs/01 §8)
- MODIFIED: `AdminSettings` — 新增 `default_monthly_token_limit`；配额日/月双限 + LLM 调用限流
- MODIFIED: `GET /me/llm-configs/models` — Redis 缓存（`models_cache_ttl_s`）
- ADDED: `POST /auth/password/change` — 登录态改密（Bearer + `old_password`/`new_password`）；旧密码错 → 401
- MODIFIED: `AdminUserItem` — 新增 `daily_token_limit`（用户级覆盖回显，null=全局默认）
- MODIFIED: `POST /auth/verify-email` — 请求体改为 `{ email, code }`（6 位数字验证码）；不再使用邮件链接 token
- ADDED: `POST /auth/resend-verification` — 重发邮箱验证码（防枚举恒 `sent: true`）
- NOTE: 异步任务由 arq/Redis 迁至 RabbitMQ（`app.messaging.worker`）；WS 事件 topic 同 RabbitMQ；Redis 仍负责用量/限流/token/检查点
- ADDED: `GET /me/llm-configs/models?provider=` — 按 provider 拉 `/models`，失败回退白名单（docs/05）
- MODIFIED: `PATCH /admin/users/{id}` — 支持 `daily_token_limit`（用户级配额覆盖，Redis `quota:user:{uid}`；显式 null 清除）
- MODIFIED: `POST /games` / `POST /games/{id}/runs` — 草稿数上限、并发 run 上限、版本保留上限；超限 429
- MODIFIED: 审批 approve/reject/take_down — 异步通知邮件 + 站内通知（docs/04 §通知）
- MODIFIED: 生成主链改用 LangGraph StateGraph（docs/02）；`SANDBOX_BACKEND=docker|local` 可选 DockerSandbox；code/qa 重试 + 沙箱/QA HITL
- NOTE: langfuse 经 `LANGFUSE_*` 环境变量启用；未配置时 trace 为空操作
- NOTE: `/play` 长缓存、`/draft` 私有短缓存（Cache-Control）

## 2026-08-06

- MODIFIED: `POST /me/llm-configs` 请求体 + `LLMConfigResp` 新增 `base_url` 字段（`openai_compat` 必填）；连通测试与 `complete()` 对 compat 使用 base_url，无 base_url → 测试失败（code-review #9） (M2/修复)
- ADDED: `POST /me/llm-configs/test` — 保存前 dry-run 连通测试（provider + model + apikey + base_url，不落库）
- MODIFIED: 连通测试由 GET `/models` 改为最小 completion；已保存配置测试补传 `base_url` + `model`；官方 provider 可选 `base_url` 覆盖（代理/私有网关）
- MODIFIED: `/play/{slug}`、`/draft/{game_id}/{version}` 的 CSP 放开 `script-src/style-src 'unsafe-inline'`——LLM 生成单文件 HTML 内联脚本，iframe `sandbox=allow-scripts`（不加 allow-same-origin）已隔离 origin，inline 不引入同源风险（code-review #1） (M5/修复)
- ADDED: `GET /admin/users`（分页，admin）、`PATCH /admin/users/{id}`（disable/role，admin，落审计）、`GET /admin/settings`、`PUT /admin/settings`（admin，存 system_settings 表，运行时配额读取覆盖值）— M8 管理后台；新增 403(非 admin)/404(用户不存在)；禁用用户登录/访问 → 403 (M8)
- ADDED: `users.disabled` 列、`system_settings` 表（迁移 0005）；`/me/usage`、`POST /games/{id}/runs` 的日配额读取 admin 设置覆盖值（env 默认回退） (M8)
- MODIFIED: `POST /games/{game_id}/publish/submit`、`GET /publish/queue`、`POST /publish/{id}/approve`、`POST /publish/{id}/reject`、`POST /games/{game_id}/take-down` — M0 桩 → M7 真实逻辑（发布审批状态机 docs/04：draft→submitted→reviewing→approved(published)/rejected，slug 在 approve 时分配；admin 操作落 audit_logs）；submit=owner，queue/approve/reject/take_down=admin；新增 401/403/404/409(状态冲突) (M7)
- MODIFIED: `POST /games/{game_id}/runs/{run_id}/hitl/resolve` — M4 桩 → M6 真实 HITL（校验 plan_confirm 检查点态 → enqueue resume_run 继续 art→done）；需 Bearer + owner；新增 409(非 HITL 态/已结束)；`GET /runs/{run_id}` 的 `current_hitl` 据检查点态返回 `{node:"plan_confirm"}` 或 null (M6)
- ADDED: 生成主链真实化——`app/forge/graph.py` 固定 DAG `plan→art→code→qa→done`（显式状态机，非 LangGraph，环境约束 + 固定 DAG 非自研 agent loop）；节点调 LLM（`app/llm/provider.complete` + `app/llm/client.call_llm` 解密用户 key + `record_usage`）+ 沙箱构建 + 产物托管 + WS 事件；HITL 在 plan_confirm 中断、Redis 检查点 `run:ckpt:{run_id}` 恢复；arq 新增 `resume_run` 任务 (M6)
- 注：M6 用显式状态机替代 docs/02 的 LangGraph（环境装不起 langgraph 重依赖；固定 DAG 非自研 agent loop）；LangGraph 替换留待环境支持时。沙箱仍用 M5 本地后端（DockerSandbox 留 ops） (M6)
- ADDED: `GET /play/{slug}`（公开，仅 published，FileResponse + CSP）、`GET /draft/{game_id}/{version}`（owner only，FileResponse + CSP）— M5 产物托管路由，根路由无 `/api/v1` 前缀；非 published/非 owner → 404 不泄露；产物响应非 JSON（text/html），openapi 标注 (M5)
- MODIFIED: `GameVersion.artifact_path` — 由桩串改为真实托管路径 `{game_id}/{version}/index.html`；forge runner 接沙箱（`LocalSandbox.execute` 本地后端）+ hosting 写真实产物 (M5)
- 注：沙箱 `execute_code` 本轮交付抽象 + 本地后端（无容器隔离），真实 docker 沙箱（`gameforge/sandbox` 镜像 + seccomp/无网络）留 M6 (M5)
- MODIFIED: `POST/GET /games`、`GET/DELETE /games/{game_id}`、`GET /games/{game_id}/versions` — M0 桩 → M4 真实逻辑（Game CRUD + versions + owner 可见性过滤，非 owner 含 admin → 404）；需 Bearer + 邮箱已验证；新增错误响应 401/403(EMAIL_NOT_VERIFIED)/404(GAME_NOT_FOUND)/409(非可删状态) (M4)
- MODIFIED: `POST /games/{game_id}/runs`、`GET /games/{game_id}/runs`、`GET /runs/{run_id}` — M0 桩 → M4 真实逻辑（发起 run + 配额检查 + 列表 + 状态）；需 Bearer + 已验证；新增 401/403/404/429(QUOTA_EXCEEDED)；`POST /games/{id}/runs/{id}/hitl/resolve` 仍桩（M6） (M4)
- 注：WS `/ws/runs/{run_id}` 事件流已真实（query token 鉴权 + Redis pubsub 转发），不进 openapi；事件契约见 docs/10 §5 (M4)
- MODIFIED: `GET /me/usage`、`GET /admin/usage` — M0 桩 → M3 真实逻辑（Redis hash 累计 today/month/total + 月榜 ZSET；/admin/usage 含 top_users）；全部需 Bearer 鉴权，新增错误响应 401(UNAUTHORIZED)/403(FORBIDDEN，/admin/usage 需 admin) (M3)
- MODIFIED: openapi 新增 `securitySchemes: bearer`（HTTPBearer）— 凡带 current_user/require_admin 的端点（me/*、admin/*、llm-config）openapi 标注需 Bearer (M1-M3 渐进)
- MODIFIED: `GET/POST /me/llm-configs`、`PATCH/DELETE /me/llm-configs/{config_id}`、`POST /me/llm-configs/{config_id}/test` — M0 桩 → M2 真实逻辑（Fernet 加密 apikey + `/v1/models` 连通测试 + 默认互斥 + ownership 过滤），全部需 Bearer 鉴权（me-scoped）；新增错误响应 400(LLM_CONFIG_INVALID 连通失败)/404(LLM_CONFIG_NOT_FOUND)/409(删除默认配置需先指定新默认) (M2)
- ADDED: 错误码 `LLM_CONFIG_NOT_FOUND`(404) — docs/10 §3 表新增 (M2)
- MODIFIED: `POST /auth/register|login|refresh|verify-email|password/reset|password/reset/confirm|logout` — M0 桩 → M1 真实逻辑（argon2/JWT/refresh rotation/邮件队列）；新增错误响应 401(UNAUTHORIZED)/409(EMAIL_TAKEN)/429(RATE_LIMITED)/400(token 无效)，openapi 已标注 (M1)
- MODIFIED: `POST /auth/logout` — 新增请求体 `{refresh_token}`（登出需撤销 refresh）；响应仍 204 无体 (M1)
- ADDED: 契约目录骨架（openapi.json 占位 + CHANGELOG + INTEGRATION）— 前端类型生成与 Mock 可起步 (M0)
- ADDED: M0 契约冻结 — FastAPI 桩路由全量上线，`contracts/openapi.json` 由 `uv run python -m app.export_openapi` 生成真实内容（23 条 HTTP 路径 + 请求/响应 schema），前端可 `pnpm gen:api` 覆盖 `types.gen.ts` (M0)
  - auth: `POST /auth/register|login|refresh|verify-email|password/reset|password/reset/confirm|logout`（logout 为 204 无响应体）
  - llm-config: `GET/POST /me/llm-configs`、`PATCH/DELETE /me/llm-configs/{id}`、`POST /me/llm-configs/{id}/test`
  - games: `POST/GET /games`（GET 分页 `PaginatedData`）、`GET/DELETE /games/{id}`、`GET /games/{id}/versions`
  - runs: `POST /games/{id}/runs`、`GET /games/{id}/runs`、`GET /runs/{run_id}`、`POST /games/{id}/runs/{run_id}/hitl/resolve`
  - publish: `POST /games/{id}/publish/submit`、`GET /publish/queue`、`POST /publish/{id}/approve|reject`、`POST /games/{id}/take-down`
  - usage: `GET /me/usage`、`GET /admin/usage`
  - 健康检查：`GET /healthz`
  - WS `/ws/runs/{run_id}` 不进 OpenAPI（浏览器原生 WS 无 schema），事件契约见 docs/10 §5
- ADDED: docs/10 §4 未列出的两个最小响应 schema — `GameDeleteResp`（DELETE /games/{id}）、logout 用 204 (M0)
