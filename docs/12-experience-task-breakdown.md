# 12 · 体验增强任务拆分（前后端 Agent）

> **依据**：[11-experience-requirements.md](11-experience-requirements.md)（2026-08-07 确认）  
> **用途**：直接复制下方「Agent 提示词」块，分别发给后端 / 前端 Agent。  
> **契约**：凡涉及 API / WS，先改 [10-contract-and-parallel-dev.md](10-contract-and-parallel-dev.md) + [contracts/CHANGELOG.md](../contracts/CHANGELOG.md)，再写代码。

---

## 1. 总览

### 1.1 三批交付顺序

| 批次 | 需求 | 建议周期 | 前后端可否并行 |
|---|---|---|---|
| **Batch A** | R1 + R3 + R4 | 第 1 周 | 契约冻结后可并行 |
| **Batch B** | R2 + R5 | 第 2 周 | R5 依赖 forge；R2 可与 R5 后端并行 |
| **Batch C** | R6 + R7 | 第 3 周 | 契约冻结后可并行 |

### 1.2 依赖关系

```text
Batch A
  后端 B-A1 官方游戏 seed ──► 后端 B-A2 fork API ──► 前端 F-A2 一键开局 UI
  后端 B-A3 WS 人话字段 ──► 前端 F-A3 阶段卡片
  后端 B-A4 结构化 design_doc ──► 前端 F-A4 HITL 分栏
  后端 B-A5 run retry ──► 前端 F-A5 失败三选一
  后端 B-A6 version activate ──► 前端 F-A6 版本时间线

Batch B
  后端 B-B1 templates API + CI ──► 前端 F-B1 模板选择器
  后端 B-B2 entry_phase 路由 ──► （前端无模式按钮，Forge 保持单入口）

Batch C
  后端 B-C1 profile 字段 ──► 后端 B-C2 公开主页 API ──► 前端 F-C1/F-C2
  后端 B-C3 reactions ──► 前端 F-C3 点赞收藏
  后端 B-C4 featured admin ──► 前端 F-C4 精选区块
  前端 F-C5 分享海报（纯前端，可任意批次插入）
```

### 1.3 本期新增契约一览（实现前写入 docs/10）

| 方法 | 路径 | 归属 |
|---|---|---|
| GET | `/api/v1/official-games` | R1 |
| POST | `/api/v1/games/fork/{slug}` | R1 |
| POST | `/api/v1/games/{game_id}/versions/{version}/activate` | R4 |
| POST | `/api/v1/runs/{run_id}/retry` | R3 |
| GET | `/api/v1/templates` | R2 |
| PATCH | `/api/v1/me/profile` | R6 |
| GET | `/api/v1/u/{handle}` | R6 |
| POST/DELETE | `/api/v1/games/{game_id}/like` | R7 |
| POST/DELETE | `/api/v1/games/{game_id}/favorite` | R7 |
| GET | `/api/v1/me/favorites` | R7 |
| GET | `/api/v1/games/featured` | R7 |
| PATCH | `/api/v1/admin/games/{game_id}/featured` | R7 |
| WS | `phase_start` 增 `human_label`, `eta_seconds` | R3 |
| WS | `hitl_wait.design_doc` 结构化 JSON | R3 |
| Run | `entry_phase`: `plan` \| `code` | R5 |

---

## 2. Batch A — 工坊体验（R1 + R3 + R4）

### 后端任务

| ID | 任务 | 产出 |
|---|---|---|
| **B-A1** | 官方预置游戏 seed | 3 款 published 游戏 + 托管产物 + 固定 slug |
| **B-A2** | 官方列表 + Fork | `GET /official-games`、`POST /games/fork/{slug}` |
| **B-A3** | WS 阶段人话 | `phase_start` 带 `human_label` / `eta_seconds` |
| **B-A4** | 结构化策划稿 | `plan_node` 输出 JSON；HITL payload 结构化；纯文本 fallback |
| **B-A5** | 失败重试 | `POST /runs/{id}/retry` 从失败检查点续跑 |
| **B-A6** | 版本回滚 | `POST /games/{id}/versions/{v}/activate` 更新 `current_version` |

### 前端任务

| ID | 任务 | 产出 |
|---|---|---|
| **F-A1** | 新手引导 | 3 步 modal，可 Skip，`localStorage` 记完成态 |
| **F-A2** | 一键开局 | Landing / `/games` 空状态官方游戏卡：试玩 / Fork / 空白创建 |
| **F-A3** | 阶段卡片 | `StagePipeline` 四阶段 + 人话 + ETA |
| **F-A4** | 结构化 HITL | `HitlCard` 分栏 Gameplay / Controls / Levels |
| **F-A5** | 失败三选一 | `FailureRecoveryBar`：改需求 / 重试 / 联系管理员 |
| **F-A6** | 版本时间线 | `VersionTimeline` + 预览切换 + 「设为当前版本」 |

---

### 【后端 Agent】B-A1 · 官方预置游戏 Seed

```
仓库：autoGame/backend。先读 docs/11 §R1、app/hosting/store.py、app/models/game.py。

任务：写入 3 个官方 published 小游戏（不消耗用户 LLM）。

要求：
1. 新增 backend/scripts/seed_official_games.py（或 alembic data migration）
2. 使用专用 system 用户（如 official@gameforge.internal）或 owner_id 固定 UUID
3. 三款：霓虹贪吃蛇 / 像素跑酷 / 塔防雏形 — 各含：
   - games 行：status=published, slug 固定（如 official-neon-snake）
   - game_versions v1 + HOSTING_ROOT 下真实 index.html（可手写最小可玩 HTML）
   - play_count 可为 0
4. idempotent：重复执行不 duplicate slug
5. README 或 scripts 注释说明：uv run python -m scripts.seed_official_games

禁止：平台 demo LLM Key；禁止硬编码玩法进 forge 业务逻辑（仅 seed 静态产物）。

验收：uv run pytest；/play/{slug} 可访问三款。
```

---

### 【后端 Agent】B-A2 · 官方游戏列表 + Fork

```
先改 docs/10 §4 + contracts/CHANGELOG，再实现。

GET /api/v1/official-games
- 无需登录
- data[]: { slug, title, description, play_url, thumbnail_url|null }

POST /api/v1/games/fork/{slug}
- 需 Bearer + 邮箱已验证
- 从官方 published 游戏复制：title（加后缀）、requirement、可选复制 v1 产物到新 game 的 v1
- 新 game status=draft, owner=当前用户, current_version=1
- 不调用 LLM，不 enqueue run
- 草稿数上限校验保持

测试：tests/test_official_games.py
导出 openapi：uv run python -m app.export_openapi
```

---

### 【后端 Agent】B-A3 · WS 阶段人话字段

```
先读 app/forge/events.py、app/forge/graph.py、docs/10 §5 WS。

在 publish_event(PHASE_START) 时增加：
- human_label: 中文人话（如「正在整理玩法说明」）
- eta_seconds: 可选整数（配置表或 settings 静态映射 plan/art/code/qa）

四阶段映射写 app/forge/phase_labels.py，方便 i18n 后续扩展。

测试：test_runs 或 test_ws 断言 payload 含 human_label。
更新 docs/10 WS schema + CHANGELOG。
```

---

### 【后端 Agent】B-A4 · 结构化 design_doc + HITL

```
先读 app/forge/graph.py plan_node、_pause_hitl。

1. PLAN_PROMPT 要求 LLM 输出 JSON：title, gameplay, controls, levels[]
2. 解析失败时 fallback：整段文本塞进 gameplay 字段
3. hitl_wait payload.design_doc 用结构化对象（非嵌套字符串）
4. 检查点 Redis 存同样结构
5. resolve modify 时合并用户意见回 plan 或直接进入 art（保持现有流程）

测试：单测 JSON 解析 + 一次 plan HITL integration mock。
契约：docs/10 hitl_wait 示例 JSON。
```

---

### 【后端 Agent】B-A5 · Run 失败重试

```
POST /api/v1/runs/{run_id}/retry
- owner only；run 状态 failed 或 paused 且检查点为 sandbox_failed|qa_failed
- 从对应 phase 重新 enqueue（不清版本号；成功后仍递增新版本）
- 返回 { run_id, status: running, phase }

与现有 resume_run 区分：resume 用于 HITL/pause；retry 用于失败恢复。

前端 R3「重试本阶段」调此接口。

测试 + 契约 + CHANGELOG。
```

---

### 【后端 Agent】B-A6 · 版本 Activate（回滚）

```
先读 docs/11 §R4、app/games/services.py list_versions。

POST /api/v1/games/{game_id}/versions/{version}/activate
- owner only
- 校验 GameVersion 存在
- 更新 games.current_version = version（不删更高版本文件）
- 可选：把该 version 的 design_doc 写回 game 上下文字段供下次 run 使用
- 响应 GameResp

状态限制：draft/rejected/taken_down 可 activate；published 仅影响后续 submit 版本号，不自动改线上 slug 指向（线上仍走 publish 审批）。

测试：activate 后 current_version 变化；新 run 产生 version+1。
契约 + CHANGELOG。
```

---

### 【前端 Agent】F-A1 · 新手引导 Modal

```
仓库：autoGame/frontend。先读 docs/11 §R1、docs/08-frontend.md。

新建 components/onboarding/OnboardingModal.tsx：
- 3 步：试玩官方示例 → 配置 LLM Key → 进入 Forge
- 每步有 Skip / 下一步；完成或 Skip 写 localStorage key onboarding_v1_done
- 触发：首次登录且 onboarding_v1_done 未设置（在 AppShell 或 RootRedirect）

不阻塞：老用户、已完成用户不再弹出。

i18n：messages.ts 补 key。vitest：localStorage mock 测试显示逻辑。
```

---

### 【前端 Agent】F-A2 · 一键开局（官方游戏卡）

```
依赖：后端 B-A2（未完成前 Mock GET /official-games）。

1. api/official.ts：listOfficialGames()、forkOfficial(slug)
2. components/onboarding/OfficialGameCards.tsx
   - 按钮：试玩 → /play/{slug}；基于此创作 → fork 后 navigate /forge/{gameId}；从空白创建 → /forge
3. 挂载点：
   - LandingPage「快速开始」区
   - GameDashboard 列表为空时
4. Fork 失败 toast；试用账号 isTrialUser 规则与现网一致

pnpm test && pnpm build。
```

---

### 【前端 Agent】F-A3 · 阶段卡片 StagePipeline

```
依赖：后端 B-A3（无 human_label 时用本地 fallback 映射）。

新建 components/forge/StagePipeline.tsx，替换或增强 RunTimeline 中部：
- 四阶段：plan / art / code / qa
- 状态：pending | active | done | failed（来自 WS phase_start + run status）
- 展示 human_label、eta 文案（如「约 1–3 分钟」）
- 不展示 tool 名

ForgePage 接入；forge-events.ts 更新 state。

vitest：给定 WS 事件序列，阶段状态正确。
```

---

### 【前端 Agent】F-A4 · 结构化 HitlCard

```
依赖：后端 B-A4。

改 components/forge/HitlCard.tsx：
- design_doc 为对象时分栏：Gameplay / Controls / Levels（levels 为列表）
- 字符串 fallback：整段显示在 Gameplay
- modify 意见 textarea 保持

forge-events.ts 类型更新 ws-types。

测试：HitlCard snapshot 或 props 单测。
```

---

### 【前端 Agent】F-A5 · 失败三选一 FailureRecoveryBar

```
依赖：后端 B-A5（retry API）。

新建 components/forge/FailureRecoveryBar.tsx，在 ForgePage 底部或 Hitl 区上方：
- 改需求：focus Chat，预填模板文案
- 重试本阶段：gamesApi.retryRun(runId)
- 联系管理员：复制 run_id 到剪贴板 + mailto（VITE_SUPPORT_EMAIL 可选）

触发：runStatus=failed 或 hitl node=sandbox_failed|qa_failed。

api/games.ts 增加 retryRun。
```

---

### 【前端 Agent】F-A6 · 版本时间线 VersionTimeline

```
依赖：后端 B-A6（activate API）。

新建 components/forge/VersionTimeline.tsx：
- gamesApi.listVersions(gameId)
- 列表 v1..vN，标注 active（current_version）、latest
- 点击：setPreviewUrl(/draft/{id}/{v})，不立即 activate
- 预览版本 ≠ current_version 时显示按钮「设为当前版本」→ activateVersion API

Forge 右栏 Tab：日志 | 试玩 | 版本

禁止：A/B 双屏对比。

api/games.ts：activateVersion(gameId, version)
测试：preview URL 切换逻辑单测。
```

---

## 3. Batch B — 模板 + 智能路由（R2 + R5）

### 【后端 Agent】B-B1 · 模板市场 API + CI 校验

```
先读 docs/11 §R2。

1. backend/app/forge/templates/manifest.yaml — 模板元数据 + requirement_seed + reference_artifact 路径
2. 每个模板附带 reference index.html，入库前经 sandbox execute + QA（可复用现有 qa 逻辑）标记 verified
3. GET /api/v1/templates — 仅 verified=true；data[]: { template_id, title, description, tags[], requirement_seed }
4. tests/test_templates.py — CI 对每个模板：产物存在、playtest PASSED

Admin 上传本期不做；manifest 随仓库发布。

契约 docs/10 + CHANGELOG + export openapi。
```

---

### 【后端 Agent】B-B2 · 智能迭代 entry_phase 路由

```
先读 docs/11 §R5、app/forge/graph.py route_start、app/games/services create_run。

1. generation_runs 表增 entry_phase（plan|code），默认 plan
2. create_run 前：规则 + 可选轻量 LLM 分类用户 requirement：
   - 小改 → entry_phase=code，继承 current_version.design_doc + 用户文本
   - 大改 → entry_phase=plan
3. graph route_start：entry_phase=code 跳过 plan_node 与 plan HITL，进 art 或直进 code（产品定：小改建议直进 code）
4. 日志/指标记录路由结果供验证

禁止：前端双按钮；路由对用户透明。

测试：parametrize 小改/大改 prompt 断言 entry_phase 与首 phase。
契约：RunCreate 响应或 GET run 含 entry_phase。
```

---

### 【前端 Agent】F-B1 · 模板选择器 TemplatePicker

```
依赖：B-B1。

1. api/templates.ts — listTemplates()
2. components/forge/TemplatePicker.tsx — 网格卡片，标签筛选
3. 入口：Forge 无 gameId 时、Onboarding 第三步、Landing「从模板开始」
4. 选中：navigate /forge?template={id} 或 createGame 后预填 Chat requirement_seed

R5 不在 UI 暴露大改/小改；Chat 仍单一发送按钮。

i18n + vitest + pnpm gen:api（契约更新后）。
```

---

## 4. Batch C — 主页 + 轻社交（R6 + R7）

### 【后端 Agent】B-C1 · 用户 Profile 字段

```
Alembic migration：
- users.handle VARCHAR unique nullable
- users.display_name VARCHAR nullable
- users.profile_public BOOLEAN default true

PATCH /api/v1/me/profile
- body: { handle?, display_name?, profile_public? }
- handle 校验：^[a-z0-9_]{3,32}$，唯一性 409
- 响应 UserProfile

GET /api/v1/me/profile — 当前用户资料回显

测试 + 契约。
```

---

### 【后端 Agent】B-C2 · 公开创作者主页

```
GET /api/v1/u/{handle}
- 无需登录；profile_public=false → 404
- data: { handle, display_name, total_plays, latest_published_at, games[] }
- games[]: 仅 published — { game_id, title, slug, play_count, published_at }

游戏列表 API 的 GameListItem / PublicGame 增 creator: { handle, display_name }（可选，供卡片展示）

测试：published 可见；draft 不出现在主页。
契约 docs/10。
```

---

### 【后端 Agent】B-C3 · 点赞 / 收藏

```
表 game_reactions(id, user_id, game_id, type enum like|favorite, created_at)
UNIQUE(user_id, game_id, type)

POST /api/v1/games/{game_id}/like — toggle
POST /api/v1/games/{game_id}/favorite — toggle
GET /api/v1/me/favorites — 分页收藏列表

公开游戏详情增 like_count, favorite_count（GET /play meta 或 GET /games/public/{slug}）

仅 published 可 like/favorite；未登录 401。

测试 + 契约。
```

---

### 【后端 Agent】B-C4 · 本周精选（Admin）

```
games 表增 featured_rank INT nullable 或 featured_until TIMESTAMPTZ

PATCH /api/v1/admin/games/{game_id}/featured — admin；body { featured_rank } 或 { featured_until }
GET /api/v1/games/featured — 公开；按 featured_rank 排序，仅 published

审计日志记录 admin 操作。

测试 + 契约。
```

---

### 【前端 Agent】F-C1 · Profile 设置 + 创作者页

```
依赖：B-C1、B-C2。

1. Settings 增 ProfilePanel：handle、display_name、公开主页开关
2. 新路由 /u/:handle → pages/creator/CreatorPage.tsx
3. 展示作品墙 + 总游玩 + 最新发布

routes.tsx 注册；未登录可访问公开主页。
```

---

### 【前端 Agent】F-C2 · 「由 @handle 创作」链接

```
依赖：B-C2 creator 字段。

GameCard、PlayPage、OfficialGameCards（若非官方）展示创作者链接 → /u/{handle}
官方三款显示「GameForge Official」无个人主页。

i18n + 样式与现有 Library 一致。
```

---

### 【前端 Agent】F-C3 · 点赞 / 收藏 UI

```
依赖：B-C3。

PlayPage 或游戏卡：心形 like、收藏星；需登录 toggle
Settings 或 /games 增「我的收藏」Tab

api/reactions.ts；TanStack Query invalidate。
```

---

### 【前端 Agent】F-C4 · 本周精选区块

```
依赖：B-C4。

LandingPage + 未来 Discover 页：FeaturedGamesStrip 读 GET /games/featured
AdminPage 已发布 Tab 增「设为精选」操作

与 R1 官方游戏区区分开：官方= onboarding；精选= curated UGC。
```

---

### 【前端 Agent】F-C5 · 分享海报（纯前端）

```
无后端依赖，可与 Batch A 并行。

components/share/SharePosterModal.tsx：
- 输入：游戏 title、slug
- canvas 绘制：标题 + QR（qrcode 库）→ /play/{slug} + GameForge logo 文案
- 下载 PNG

入口：PlayPage、GameCard（published）

vitest：mock canvas。
```

---

## 5. 联调验收清单（全量）

| # | 场景 | 通过标准 |
|---|---|---|
| 1 | 新用户无 LLM Key | 可试玩 3 官方游戏；不可 run |
| 2 | Fork 官方游戏 | 得到自己 draft v1，可进 Forge |
| 3 | 生成中 | 四阶段卡片有人话 + ETA |
| 4 | 策划 HITL | 分栏展示；批准后继续 |
| 5 | 生成失败 | 三选一可用；重试可续跑 |
| 6 | 多版本 | 时间线切换预览；activate 回滚 |
| 7 | 模板 | 选模板预填；用户 run 消耗自己 Key |
| 8 | 小改 prompt | 无 UI 模式按钮；后端 entry_phase=code |
| 9 | 创作者主页 | /u/handle 仅 published |
| 10 | 社交 | like/favorite/精选/海报下载 |

```bash
# 后端
cd backend && uv run pytest -q && uv run ruff check .

# 前端
cd frontend && pnpm gen:api && pnpm test && pnpm build && pnpm smoke:real
```

---

## 6. 修订记录

| 日期 | 说明 |
|---|---|
| 2026-08-07 | 初版：R1–R7 拆为 Batch A/B/C，共 6+6+5+5 条前后端任务 + Agent 提示词 |
