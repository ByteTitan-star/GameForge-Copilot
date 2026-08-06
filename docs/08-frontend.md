# 08 · 前端

> 页面与组件概览。精确 schema、类型同源、Mock 策略、并行里程碑见 [10-contract-and-parallel-dev.md](10-contract-and-parallel-dev.md)。

## 技术栈

- React + Vite + TypeScript（严格模式）
- Tailwind CSS + shadcn/ui（组件优先，少造轮子）
- 状态：TanStack Query（服务端态）+ Zustand（本地态）
- WS：原生 + 轻封装，token 经 `?token=` 查询参数传（浏览器限制）
- pnpm 管理依赖

## 页面

### 1. 认证页
- 登录 / 注册 / 邮箱验证 / 密码重置。
- 注册成功提示去查邮件；未验证账号登录后引导去 setting 配 LLM 并提示验证邮箱。

### 2. 设计页（核心）
- 多轮对话 UI，左侧消息流，右侧实时生成进度面板。
- WS 连 `/ws/runs/{run_id}`，展示 `phase_start` / `tool_call` / `build_done` / `qa_report` 等事件。
- 策划稿 HITL：弹卡片让用户确认/修改，确认后继续。
- 生成完成：右侧切到试玩视图，可直接玩。
- 顶部：发起新游戏、迭代修改、提交发布。

### 3. 我的游戏页
- 草稿列表（status=draft/rejected）、已发布列表。
- 每条：标题、状态、版本、试玩/编辑/提交发布/删除。

### 4. 试玩页
- `/play/{slug}`：公开，**必须用 `<iframe sandbox="allow-scripts">` 挂载产物**（不加 allow-same-origin，隔离同源 cookie/存储），无登录要求。
- `/draft/{game_id}/{version}`：鉴权 owner，同 sandbox 挂载，预览未发布版本。

### 5. Setting 页
- LLM 配置管理：provider 选择、apikey 输入（掩码）、模型选择、连通测试、设默认。
- 我的用量看板：日/月/累计 token 与调用次数、配额余量。
- 账号：改密码、邮箱验证状态。

### 6. 管理后台（admin）
- 审批工作台：待审队列，通过/驳回（理由）。
- 已发布游戏管理：列表、下架。
- 用户管理：列表、禁用、角色切换、配额覆盖。
- 系统用量：总量趋势 + 每用户 Top。
- 全局设置：默认配额、限流参数等。

## 组件要点

| 组件 | 说明 |
|---|---|
| `ChatPanel` | 对话消息流 + 输入框，支持流式文本增量渲染 |
| `RunProgress` | 生成进度面板，按子图阶段展示，事件驱动 |
| `HitlCard` | 策划稿/自检失败确认卡片 |
| `GamePlayer` | 试玩容器，按版本/类型加载产物 |
| `UsageChart` | 用量图表（用 Chart 库，中文注意字体——见历史教训） |
| `GameCard` | 游戏列表项 |

## 实时进度交互

1. 用户发起 run → 后端返回 `run_id` → 前端连 WS。
2. 后端每个节点/工具/LLM 调用发事件 → WS 推送 → 前端增量渲染。
3. HITL 节点：前端收到 `hitl_wait` → 展示卡片 → 用户操作 → POST 对应接口 → 后端续跑。
4. 断线重连：前端按 `run_id` 重连，后端从检查点恢复并补发当前阶段状态。

## 工程约定

- 路由：React Router，受保护路由按角色守卫。
- API 封装：`src/api/` 集中，TanStack Query 缓存。
- 类型：后端 schema 用 openapi-typescript 生成类型，前后端类型同源。
- 错误：统一 toast/inline，网络错误重试有限次后提示。
- 测试：vitest，公共组件/工具函数补测试。
- 构建：`pnpm build` 产物给后端静态托管或独立部署。

## 不做

- 不在业务代码里硬编码游戏 UI/玩法——试玩容器是通用的。
- 不为单一游戏特化组件。
