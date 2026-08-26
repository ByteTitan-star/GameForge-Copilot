# 三大一级模块设计：模板中心 / 创作者中心 / 消息中心

- 日期：2026-08-25
- 状态：**待用户审查**
- 范围：产品一级导航新增 3 个平级模块（与「我的游戏 / 创作工坊 / 发现 / 设置」同级）
- 原则：YAGNI —— 聚合已有能力，不另起产品线

---

## 1. 背景与目标

### 1.1 现状

| 已有模块 | 路由 | 职责 |
| --- | --- | --- |
| 我的游戏 | `/games` | 草稿、版本、发布状态 |
| 创作工坊 | `/forge` | AI 生成与试玩 |
| 发现 | `/discover` | 社区公开作品浏览 |
| 设置 | `/settings` | 账号、LLM、主题、用量 |
| 管理平台 | `/admin` | 运营（管理员） |

**能力已存在但分散：**

- 模板：`GET /api/v1/templates`、`TemplatePicker`、Forge 内嵌、onboarding 官方示例
- 创作者：`/u/:handle` 公开主页、`GET /api/v1/creator/:handle`、单游戏 analytics
- 通知：`notifications` 表、`GET/POST /api/v1/me/notifications`、`NotificationBell` 弹层

### 1.2 目标

新增三个一级入口，让用户**不用在 Forge / 发现 / 设置之间来回找**：

1. **模板中心** —— 解决「怎么开始」
2. **创作者中心** —— 解决「作品怎么经营」（仅本人视角）
3. **消息中心** —— 解决「系统结果去哪看」

### 1.3 非目标

- 社区模板投稿、模板市场结算
- 粉丝关注、私信、评论系统
- 团队空间、多人共编
- 浏览器 Push / 邮件模板改版（沿用现有 `notify_user` + 邮件队列）
- 重做侧栏信息架构（仅增项 + 微调顺序）

---

## 2. 导航与信息架构

### 2.1 侧栏顺序（登录用户）

```
我的游戏 → 创作工坊 → 模板中心 → 发现 → 创作者中心 → 消息中心 → 设置
（管理员额外：管理平台）
```

### 2.2 路由

| 模块 | 路由 | 鉴权 |
| --- | --- | --- |
| 模板中心 | `/templates` | 登录用户（试用账号可读） |
| 创作者中心 | `/creator` | 登录用户（试用只读部分数据） |
| 消息中心 | `/messages` | 登录用户 |
| 公开创作者主页 | `/u/:handle` | 保持现状，不改路由 |

### 2.3 铃铛行为

- **保留**顶部 `NotificationBell` 作为快捷预览（最近 5 条 + 未读角标）
- 弹层底部增加 **「查看全部」** → `/messages`
- 侧栏「消息中心」与铃铛共享同一 `['notifications']` query

---

## 3. 模块 A：模板中心

### 3.1 用户故事

> 我想先逛一逛能做什么类型的游戏，试玩样例，再一键带着需求进工坊。

### 3.2 页面结构

```
/templates
├── 页头：标题 + 一句话说明
├── 区块 1：官方示例（复用 OfficialGameCards）
│   └── 试玩 / 基于此创作（已有 official fork API）
├── 区块 2：玩法模板库（复用 TemplatePicker 的数据与卡片样式，全页布局）
│   ├── 标签筛选（action / casual / puzzle …）
│   ├── 模板卡片：标题、描述、标签、引擎徽标
│   └── 操作：[试玩]（playable 时） / [用此模板创作]
└── 空态 / 加载 / 错误（与发现页一致）
```

### 3.3 核心交互

| 操作 | 行为 |
| --- | --- |
| 用此模板创作 | `navigate('/forge', { state: { templateId, requirementSeed } })` 或创建新 game 后跳转（与 Forge 现有 template 选择逻辑对齐） |
| 试玩 | `play_url` → `/play/template/:id` |
| 官方示例 · 基于此创作 | 复用 `officialApi.fork` → `/forge/:gameId` |

### 3.4 后端

**MVP 无需新 API。** 继续用：

- `GET /api/v1/templates`
- `GET /api/v1/official-games`

可选增强（非 MVP）：`templates` 响应增加 `cover_url` 字段（若 catalog 有 reference artifact）。

### 3.5 与 Forge 的关系

- Forge 内 `TemplatePicker` **保留**（创作中换模板仍可用）
- 模板中心是**独立入口**，不负责生成过程
- onboarding 第三步「进入工坊」可改为链到 `/templates` 或保持直达 `/forge`（实现时二选一，推荐链模板中心）

### 3.6 试用账号

- 可浏览、可试玩模板
- 「用此模板创作」引导注册（与现有 trial 限制一致）

---

## 4. 模块 B：创作者中心

### 4.1 用户故事

> 我想在一个地方看到我的公开主页、作品数据、审核中的稿，而不是散落在「我的游戏」和设置里。

### 4.2 与 `/u/:handle` 的分工

| | 公开主页 `/u/:handle` | 创作者中心 `/creator` |
| --- | --- | --- |
| 观众 | 任何人 | 仅本人 |
| 内容 | 已发布作品列表 | 经营仪表盘 + 快捷操作 |
| 数据 | 总播放量、最近发布 | 分作品 PV/UV、收藏数、审核状态 |

### 4.3 页面结构

```
/creator
├── 页头：展示名、@handle、[预览公开主页] → /u/:handle
├── 概览卡片（4 格）
│   ├── 已发布作品数
│   ├── 累计试玩（sum play_count）
│   ├── 待审核数
│   └── 草稿数
├── 区块：已发布作品
│   └── 卡片含 play_count、30d PV/UV（调用已有 GET /me/games/{id}/analytics）
├── 区块：审核中 / 最近草稿（各最多 5 条，[查看全部] → /games?filter=…）
└── 快捷操作：[新建游戏] → /forge、[编辑资料] → /settings?tab=profile
```

### 4.4 后端

**MVP：聚合现有 API，无新表。**

前端并行请求：

- `GET /api/v1/me` 或 profile 接口（handle、display_name）
- `GET /api/v1/games`（按 status 分组）
- 对每个已发布且有 slug 的游戏：`GET /api/v1/me/games/{game_id}/analytics`

可选增强（P2，减轻 N+1）：

```
GET /api/v1/me/creator-dashboard
→ { profile, stats, published: [{ game, analytics }], pending, drafts }
```

### 4.5 试用账号

- 只读：展示资料与空态提示
- 隐藏或禁用「新建」「编辑发布」类 CTA，文案指向注册

### 4.6 非目标

- 粉丝数、关注列表
- 收入 / 打赏
- 评论管理

---

## 5. 模块 C：消息中心

### 5.1 用户故事

> 审核通过/驳回、配额用尽、生成失败等通知，我想有个固定页面能翻历史、点进去处理。

### 5.2 页面结构

```
/messages
├── 页头：标题 + [全部标为已读]
├── 筛选 Tab：全部 | 发布 | 系统 | 配额
├── 列表项：图标(kind) + 标题 + 摘要 + 相对时间 + 未读点
└── 空态：暂无通知
```

### 5.3 通知类型（沿用现有 `kind`）

| kind | 分类 Tab | 典型场景 | 跳转目标（MVP） |
| --- | --- | --- | --- |
| `publish_approved` | 发布 | 审核通过 | `/games` 或 `/play/:slug` |
| `publish_rejected` | 发布 | 审核驳回 | `/games` + 对应游戏 |
| `take_down` / `republish` | 发布 | 下架/重新上架 | `/games` |
| `quota` | 配额 | 日 token 用尽 | `/settings?tab=…` 用量 |
| `system_quota` | 系统 | 管理员告警 | `/admin`（仅 admin） |
| **新增** `run_completed` | 系统 | 生成成功 | `/forge/:gameId` |
| **新增** `run_failed` | 系统 | 生成失败 | `/forge/:gameId` |

### 5.4 后端改动

#### 5.4.1 通知表扩展（推荐，小迁移）

```sql
ALTER TABLE notifications ADD COLUMN action_url VARCHAR(512) NULL;
```

- `NotificationItem` 增加可选字段 `action_url`
- `notify_user(..., action_url: str | None = None)`
- 发布/配额等现有调用点补 `action_url`

#### 5.4.2 新通知触发点

在 run 终态（`completed` / `failed`）时调用 `notify_user`（**仅当用户不在该 forge 页或不保证 WS 送达时也可发**，MVP 可一律发）。

#### 5.4.3 新 API

```
POST /api/v1/me/notifications/read-all
→ { updated: number }
```

列表 API 增加可选参数：`kind_prefix` 或 `category`（前端也可先本地 filter）。

### 5.5 铃铛弹层

- 展示最近 5 条
- 点击项：标已读 + 若有 `action_url` 则 `navigate`
- 底部「查看全部」→ `/messages`

### 5.6 非目标

- 用户间私信
- 通知偏好设置（邮件开/关）
- 实时 WebSocket 推送新通知（仍依赖进入页面/铃铛轮询或 invalidate）

---

## 6. 实现分期

| 阶段 | 内容 | 预估 |
| --- | --- | --- |
| **P1** | 模板中心：路由 + 页面 + 侧栏 + i18n | 小 |
| **P2** | 消息中心：全页 + read-all + action_url 迁移 + run 完成/失败通知 | 中 |
| **P3** | 创作者中心：仪表盘页 + analytics 聚合 | 中 |
| **P4**（可选） | `GET /me/creator-dashboard` 合并接口 | 小 |

**推荐顺序：P1 → P2 → P3**（模板最快验证导航价值；消息依赖小迁移；创作者可最后聚合）。

---

## 7. 前端文件清单（预估）

| 新增/改动 | 说明 |
| --- | --- |
| `pages/templates/TemplatesPage.tsx` | 模板中心 |
| `pages/creator/MyCreatorPage.tsx` | 创作者中心（勿与 `CreatorPage` 公开页混淆） |
| `pages/messages/MessagesPage.tsx` | 消息中心 |
| `routes.tsx` | 注册 3 路由 |
| `AppShell.tsx` | 侧栏 3 项 |
| `NotificationBell.tsx` | 查看全部 + action 跳转 |
| `i18n/messages.ts` | 文案键 |
| `api/me.ts` | `markAllNotificationsRead`（若后端新增） |

复用组件：`TemplatePicker` 卡片逻辑、`OfficialGameCards`、`PublicGameCard`、`GameCard`、`StatusBadge`。

---

## 8. 验收标准

### 模板中心

- [ ] 侧栏可进入 `/templates`，展示官方示例 + API 模板列表
- [ ] 可试玩 playable 模板
- [ ] 「用此模板创作」进入 Forge 且预填 `requirement_seed`
- [ ] 试用账号可浏览，创作 CTA 受 trial 规则约束

### 创作者中心

- [ ] 侧栏可进入 `/creator`，仅本人可访问
- [ ] 展示已发布/待审/草稿统计与列表
- [ ] 已发布作品展示 play_count 与 30d PV/UV
- [ ] 「预览公开主页」跳转 `/u/:handle` 正确

### 消息中心

- [ ] 侧栏可进入 `/messages`，列表与铃铛数据一致
- [ ] 支持标单条已读、全部已读
- [ ] 发布类通知可跳到对应游戏/试玩页
- [ ] 生成完成/失败产生新通知（若用户已订阅该 run）

---

## 9. 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 侧栏项过多 | 移动端收进汉堡菜单；桌面可折叠侧栏已有 |
| 创作者中心 N+1 请求 | MVP 接受；P4 合并接口 |
| `action_url` 迁移 | 可空列，旧通知无链接仍只展示文案 |
| 与 ADR-12 前端状态问题叠加 | 新页用 react-query，不扩 Forge 状态机 |

---

## 10. 修订记录

| 日期 | 说明 |
| --- | --- |
| 2026-08-25 | 首版：三模块范围、路由、分期、验收 |
