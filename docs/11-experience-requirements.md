# 11 · 体验增强需求（新增）

> **文档类型**：新增产品需求（Experience / UX）  
> **创建日期**：2026-08-07  
> **状态**：已确认，待排期实现  
> **关联**：在 [01-features.md](01-features.md) MVP 主链路（M0–M8）之上增量建设；接口变更仍遵循 [10-contract-and-parallel-dev.md](10-contract-and-parallel-dev.md)。  
> **任务拆分**：前后端 Agent 可执行清单见 [12-experience-task-breakdown.md](12-experience-task-breakdown.md)。

---

## 0. 背景与范围

GameForge-Copilot 已完成「注册 → 配 Key → 工坊生成 → 试玩 → 发布审批」主链路。本文件记录 **2026-08-07 产品侧确认** 的体验增强项，目标是：

- 降低首次成功门槛（不靠平台赠送 LLM 额度）；
- 提升生成过程可感知性与失败可恢复性；
- 强化迭代、发布、发现与轻量社交闭环。

### 0.1 本期纳入

| # | 模块 | 摘要 |
|---|---|---|
| R1 | 新手引导 + 预置试玩 | 三个官方预置小游戏，一键开局；**不提供**平台体验额度 / 固定 demo Key |
| R2 | 模板市场 | 可选模板加速创作；**后端保证**模板可产出可运行小游戏 |
| R3 | 生成过程体验 | 阶段卡片、结构化 HITL、失败三选一恢复 |
| R4 | 版本时间线 + 回滚 | Forge 右侧 v1/v2/v3 预览；支持回滚到历史版本（无 A/B 对比） |
| R5 | 智能迭代路由 | 用户只描述修改意图；**由 Agent 自动判断**大改 / 小改，不提供双按钮 |
| R6 | 创作者主页 | `/u/{handle}` 公开主页与作品墙 |
| R7 | 轻量社交 | 点赞 / 收藏、本周精选、分享海报 |

### 0.2 明确不做（本期）

| 项 | 说明 |
|---|---|
| 平台体验 LLM 额度 / 固定 demo Key | 存在恶意刷注册风险，**拒绝** |
| 邀请朋友试玩（draft 分享链） | **下一版本**再做 |
| 用量按游戏拆分、成本估算、OAuth、定时上下架、多人协作等 | 见上一轮讨论，**本期不考虑** |
| 版本 A/B 左右对比试玩 | **不做** |

---

## R1 · 新手引导 + 预置试玩（Onboarding）

### 产品目标

新用户注册后 **无需先配 LLM Key**，也能立刻理解产品价值：「描述 → 生成 → 试玩」。

### 方案（已确认）

1. **不提供**平台统一 LLM Key 或体验 token 配额（防刷号滥用）。
2. 系统内置 **三个已创建好的官方小游戏**（静态产物 + 元数据已落库/托管），例如：
   - 霓虹贪吃蛇
   - 像素跑酷
   - 塔防雏形  
   （具体标题与 slug 以实现时 seed 为准，须可公开试玩。）
3. 新用户首次进入（或 `/games` 空状态 / 落地页 CTA）展示 **「一键开局」**：
   - **试玩官方示例**：跳转 `/play/{slug}` 或内嵌预览；
   - **基于此创作**：Fork 为当前用户的 **新 draft**（复制 `requirement` + 可选复制最近版本产物作为 v1 起点，见 R2/R4 实现细节）；
   - **从空白创建**：进入 Forge，仍须自配 LLM Key 后才能发起 run。
4. **轻量引导**（3 步以内，可 Skip）：
   - Step 1：试玩一个官方示例；
   - Step 2：去 Setting 配置 LLM Key（生成自己的游戏时必需）；
   - Step 3：进入 Forge 描述或选模板。

### 验收标准

- [ ] 未配置 LLM Key 的用户可试玩三个官方游戏；
- [ ] 未配置 Key 的用户 **不能** 发起 generation run（行为与现网一致）；
- [ ] 一键 Fork 后产生 owner 为自己的 draft，不消耗 LLM；
- [ ] 引导可跳过，不阻塞老用户。

### 实现要点（供前后端拆分）

| 层 | 要点 |
|---|---|
| 后端 | seed 脚本或 migration 写入 3 款 `status=published` 的官方 game + 托管产物；可选 `POST /games/fork/{official_slug}` |
| 前端 | 空状态 / Landing / 首次登录 modal；引导状态存 `localStorage` 或 user preference |

---

## R2 · 模板市场

### 产品目标

降低「空白输入框」焦虑；模板是 **起点 prompt + 风格标签**，不是硬编码玩法。

### 方案（已确认）

1. **模板列表**（只读）：标题、描述、标签（霓虹 / 像素 / 休闲…）、`requirement_seed`。
2. 用户选模板 → 进入 Forge，Chat 预填 seed，可编辑后再生成。
3. **模板是否真能产出小游戏——由后端负责验证**，不是前端保证：

#### 模板准入与校验（后端职责）

| 阶段 | 动作 |
|---|---|
| **入库前** | 每个模板必须附带 **已验证的产物**（与官方预置游戏类似）：`index.html` 经沙箱 `execute` + QA playtest 通过，方可标记 `verified=true` |
| **发布前 CI** | `backend/tests/test_templates.py`（或同类）对全部模板跑：产物存在、大小未超限、playtest PASSED |
| **运行时** | 模板 **不单独走 LLM**；仅提供 seed 文本。用户点「用此模板生成」仍走正常 run，消耗用户 Key |
| **可选进阶** | Admin 上传新模板 → 后台触发验证 job，失败则不可上架 |

> 结论：模板市场的「输出是小游戏」靠 **预验证的 reference 产物 + 用户 run 走同一套 forge 管线** 保证；不是在业务代码里写死玩法逻辑。

### 验收标准

- [ ] `GET /api/v1/templates` 仅返回 `verified=true` 的项；
- [ ] 每个模板在 CI 中有自动化 playable 校验；
- [ ] 前端模板 picker 与 Forge 预填联动。

---

## R3 · 生成过程体验（阶段卡片 + 结构化 HITL + 失败恢复）

### 3.1 阶段卡片化

在 Forge 中部/侧栏展示四阶段：**策划 → 美术 → 代码 → 质检**。

| 字段 | 说明 |
|---|---|
| 阶段状态 | pending / active / done / failed |
| 人话描述 | 如「正在把需求整理成玩法说明」，**不直接暴露** `tool_call` 内部工具名 |
| 预计耗时 | 静态区间即可（如「约 1–3 分钟」），按历史 run P50 配置 |
| 当前动作 | 来自 WS `phase_start` / 聚合后的摘要文案 |

后端可在 WS `phase_start` payload 增加可选字段 `human_label` / `eta_seconds`（契约变更写 docs/10）。

### 3.2 策划 HITL 结构化展示

`hitl_wait`（`node=plan_confirm`）的 `design_doc` **改为结构化 JSON**（契约变更）：

```json
{
  "title": "霓虹贪吃蛇",
  "gameplay": "移动、吃豆、计分…",
  "controls": "方向键 / WASD；空格暂停",
  "levels": ["热身", "加速", "障碍"]
}
```

前端 `HitlCard` 分栏渲染；用户可填修改意见（沿用现有 modify 流程）。

后端 `plan_node`：要求 LLM 输出 JSON（或从文本解析），写入检查点；**兼容**旧 run 的纯文本 fallback。

### 3.3 失败时三选一

当 run `failed` 或 HITL `sandbox_failed` / `qa_failed` 时，前端展示：

| 选项 | 行为 |
|---|---|
| **改需求** | 聚焦 Chat 输入框，预填「请根据以下问题修改：…」 |
| **重试本阶段** | 调后端「从失败阶段重试」接口（见 R5 路由，或 `POST /runs/{id}/retry`） |
| **联系管理员** | mailto / 站内反馈链接（MVP 可 `mailto:support@…` 或复制 run_id） |

不提供第四种「静默失败」。

### 验收标准

- [ ] 四阶段卡片随 WS 更新；
- [ ] HITL 策划稿分栏展示 Gameplay / Controls / Levels；
- [ ] 失败态必出三选一，且重试可发起新 run 或 resume。

---

## R4 · 版本时间线 + 回滚

### 产品目标

用户感知「每一版生成结果」，可预览历史版本，并 **回滚到某一版作为当前工作版本**。

### 现状（仓库已有）

- 每次 code 构建成功 → `game_versions` 新增一行，`version` 单调递增；
- 产物路径：`HOSTING_ROOT/{game_id}/{version}/index.html`；
- `games.current_version` 指向 **最新成功构建的版本号**；
- `GET /games/{id}/versions` 已存在。

### 回滚在本仓库的含义（非 Git 回退）

**不是**改 Git 历史，也 **不删除** 新版本文件；而是 **切换当前生效版本指针**：

```
回滚到 v2  ≡  将 games.current_version 设为 2
            （v3 的 DB 行与磁盘产物仍保留，除非超出 max_versions_per_game 被 prune）
```

| 场景 | 行为 |
|---|---|
| **草稿预览** | Forge iframe 加载 `/draft/{game_id}/{current_version}`；时间线点击 vN 仅切换预览 URL，不必立刻写库 |
| **确认回滚** | `POST /games/{id}/versions/{version}/activate` → 校验 version 存在 → 更新 `current_version` |
| **后续迭代** | 新 run 成功后仍 **递增** 出新 version（v4…），不在旧 version 号上覆盖 |
| **提交发布** | `publish/submit` 的 `version` 字段提交 **当前选中的 version**（可与 latest 不同） |
| **已发布游戏** | 若需线上回退：提交指定旧 version 的 publish 请求，走审批（与现状态机一致） |

可选增强（非必须）：activate 时把该版本的 `design_doc` 同步进 run 上下文，便于 Agent 基于旧版继续改。

**不做**：左右双屏 A/B 对比。

### 前端

- Forge 右侧 **VersionTimeline**：v1, v2, v3…，点击切换 iframe；
- 当前预览版本与 `current_version` 不一致时，显示 **「设为当前版本（回滚）」** 按钮；
- 列表标注 latest / active / published。

### 验收标准

- [ ] 时间线可切换预览任意保留版本；
- [ ] 回滚后 `current_version` 与预览一致，新 run 从回滚版上下文继续；
- [ ] 无 A/B 对比 UI。

---

## R5 · 智能迭代路由（无大改/小改双按钮）

### 产品目标

用户用自然语言描述修改（如「背景改紫色」「加一个 Boss 关」），**系统自动决定** pipeline 入口，UI **不提供**「大改 / 小改」两个按钮。

### 方案

1. 用户仅在 Chat 输入修改意图；
2. 后端在 `create_run` 或 forge 入口增加 **路由节点**（轻量 LLM 或规则）：
   - **小改**（倾向只进 `code`，跳过 plan HITL）：颜色、数值、文案、单一机制微调；
   - **大改**（从 `plan` 或 `plan` HITL 开始）：新关卡结构、换核心玩法、大量机制变更；
3. 路由结果写入 run 元数据 `entry_phase`（契约字段），graph `route_start` 据此进入；
4. 小改时 **继承** 当前 `current_version` 的 `design_doc` + 用户 modify 文本作为 requirement。

### 验收标准

- [ ] Forge 只有单一发送入口，无模式切换按钮；
- [ ] 小改类 prompt 的 run 多数跳过策划 HITL（可日志/指标验证）；
- [ ] 大改类 prompt 仍走完整 plan → HITL。

---

## R6 · 创作者主页与作品墙

### 产品目标

给创作者 **公开身份** 与 **作品聚合页**，增强成就感与传播。

### 方案

1. 用户可设置 **`handle`**（唯一、URL 安全，`/u/{handle}`）；
2. 公开主页展示：
   - 昵称 / handle；
   - **已发布** 游戏列表（卡片，链到 `/play/{slug}`）；
   - 简单统计：总游玩次数（sum `play_count`）、最新发布作品时间；
3. 公开游戏卡、试玩页、发现页展示 **「由 @{handle} 创作」**，点击进入主页；
4. 隐私：用户可关闭公开主页（仅隐藏 `/u/{handle}`，不影响已发布 slug 试玩）。

### 数据模型（待实现）

| 表/字段 | 说明 |
|---|---|
| `users.handle` | unique, nullable → 设置后公开 |
| `users.profile_public` | bool, default true |
| `users.display_name` | optional |

### API（契约待写入 docs/10）

- `GET /api/v1/u/{handle}` — 公开主页
- `PATCH /api/v1/me/profile` — 设置 handle / display_name / profile_public

### 验收标准

- [ ] 设置 handle 后 `/u/{handle}` 可访问；
- [ ] 仅展示 published 游戏；
- [ ] 游戏卡与试玩页有创作者链接。

---

## R7 · 轻量社交

### 7.1 点赞 / 收藏

- 需登录；
- 每用户对每游戏 **点赞** 一次（toggle）；**收藏** 进「我的收藏」列表；
- 公开游戏详情/卡片展示 like_count、favorite_count（可仅展示 like）；
- 数据表：`game_reactions(user_id, game_id, type=like|favorite)`，unique(user, game, type)。

### 7.2 本周精选

- Admin 后台可 **置顶/精选** published 游戏（`featured_until` 或 `featured_rank`）；
- 发现页 / 落地页 **「本周精选」** 区块读取该列表；
- MVP 无复杂算法，**人工 curated** 即可。

### 7.3 分享海报

- 试玩页 / 游戏卡 **「生成海报」**：
  - 游戏名 + 二维码（指向 `/play/{slug}`）+ GameForge 品牌；
  - 前端 canvas 导出 PNG（MVP 不需服务端渲染）；
- 可选：使用游戏 iframe 截图或默认封面图。

### 验收标准

- [ ] 登录用户可 like / favorite；
- [ ] Admin 可配置精选，前端展示；
- [ ] 分享海报可下载 PNG。

---

## 8. 排期建议（参考）

| 批次 | 需求 | 说明 |
|---|---|---|
| **Batch A** | R1, R3, R4 |  onboarding + 过程体验 + 版本线，直接改善工坊 |
| **Batch B** | R2, R5 | 模板市场 + 智能路由，依赖 forge 稳定 |
| **Batch C** | R6, R7 | 主页 + 轻社交，依赖公开发现与 play_count |

---

## 9. 契约与文档变更清单

实现前须同步：

1. [10-contract-and-parallel-dev.md](10-contract-and-parallel-dev.md) — 新增/修改端点与 WS payload；
2. [contracts/CHANGELOG.md](../contracts/CHANGELOG.md) — 逐条记录；
3. [01-features.md](01-features.md) — 将对应行从「进阶」改为「R11 已规划」（可选，合并 PR 时做）；
4. [08-frontend.md](08-frontend.md) — 补新页面与组件索引（可选）。

---

## 10. 修订记录

| 日期 | 说明 |
|---|---|
| 2026-08-07 | 初版：产品侧确认 R1–R7 范围；明确排除平台 demo Key、邀请试玩本期不做、版本无 A/B |
