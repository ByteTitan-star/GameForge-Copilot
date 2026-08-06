# GameForge-Copilot

🎮 浏览器里的 AI 游戏工作室。用多轮对话把想法锻成**可玩的 HTML 小游戏**——描述、确认、试玩、发布。

> From prompt to playable. · 当前仓库含可跑的前端 mock 闭环（MSW）；后端并行推进中。

<p align="center">
  <img src="docs/assets/01-landing.png" alt="GameForge Landing" width="900" />
</p>

<p align="center">
  <code>描述玩法</code> → <code>HITL 确认策划</code> → <code>生成构建</code> → <code>沙箱试玩</code> → <code>提交发布</code>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#demo-cases">Cases</a> ·
  <a href="#product-ui">UI</a> ·
  <a href="#for-contributors">Contributors</a>
</p>

---

## Demo Cases

落地页里的三条样例路径（mock 库同款）。完整卡片见下图。

<p align="center">
  <img src="docs/assets/01-landing-cases.png" alt="Landing features and cases" width="900" />
</p>

| Case | 一句话开局 | 状态 | 你会看到 |
|---|---|---|---|
| **霓虹贪吃蛇** | 「方向键 + 计分，失败一键重开」 | Draft | 进工坊继续打磨、预览、提交发布 |
| **像素跑酷** | 「障碍节奏 + 皮肤切换」 | Published | 公开 slug 试玩入口 |
| **塔防雏形** | 「路径与波次先数值确认」 | Rejected → 可再提审 | HITL 改策划稿后再出可运行版 |

---

## Product UI

截图来自本地 `pnpm dev` + `VITE_USE_MOCK=true`（2026-08）。顶部绿色条是 mock 提示，不是生产文案。

### 登录 · 液态玻璃

<p align="center">
  <img src="docs/assets/02-login.png" alt="Login" width="900" />
</p>

### 我的游戏 · 深色 Library

封面卡、状态筛选、发布 / 删除。

<p align="center">
  <img src="docs/assets/03-games.png" alt="Games library" width="900" />
</p>

### 设计工坊 · 命令台三栏

左 Chat · 中 Pipeline + HITL · 右事件日志 / 试玩。

<p align="center">
  <img src="docs/assets/04-forge.png" alt="Forge console with HITL" width="900" />
</p>

### Setting · LLM Key 与用量

自带 apikey（掩码展示）+ 日/月/累计 token 看板（图表字体：Noto Sans SC）。

<p align="center">
  <img src="docs/assets/05-settings.png" alt="Settings LLM and usage" width="900" />
</p>

### 对话长什么样

```text
你：做一个霓虹贪吃蛇，方向键控制，带计分。
工坊：run xxx · mock WS 已连接
工坊：策划稿已就绪，请在中间面板确认…
—— HITL ——
Gameplay: 移动、收集、计分；失败一键重开
Controls: 方向键 / WASD；空格暂停
Levels: 热身关 · 加速关 · 障碍关
你：[批准继续] → art → code → qa → 右侧试玩
```

---

## Quick Start

```bash
git clone https://github.com/ByteTitan-star/GameForge-Copilot.git
cd GameForge-Copilot/frontend
pnpm install
cp .env.example .env   # VITE_USE_MOCK=true
pnpm dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)

| | |
|---|---|
| Mock 账号 | `demo@gameforge.dev` / `password123` |
| 管理员 | `admin@gameforge.dev` / `password123` |
| 未验证邮箱 | `unverified@gameforge.dev` / `password123` |

```bash
pnpm test    # vitest + MSW
pnpm build
```

---

## For Contributors

### 技术栈

| 层 | 选型 |
|---|---|
| 编排 | LangGraph（检查点 / HITL / 子图） |
| 后端 | Python 3.12 · FastAPI · uv |
| 前端 | React · Vite · TypeScript · Tailwind · TanStack Query · Zustand · MSW |
| 数据 | PostgreSQL · Redis |
| 沙箱 | execute_code（生成期构建） |

### 架构

```
[Web] ──HTTP/WS──▶ [FastAPI]
                     ├ forge (plan→art→code→qa)
                     ├ auth / publish / usage
                     └ hosting /play/{slug}
```

### 文档与契约

- [docs/](docs/) — 功能 / 架构 / 生成 / 托管 / 用量 / 认证 / API / 前端 / 部署
- [docs/10-contract-and-parallel-dev.md](docs/10-contract-and-parallel-dev.md) — **契约圣经**
- [contracts/](contracts/) — `openapi.json` · `CHANGELOG.md` · `INTEGRATION.md`（前后端靠 git 协作，不轮询）

约定见 [CLAUDE.md](CLAUDE.md)。截图资源在 [docs/assets/](docs/assets/)。

### 里程碑（摘要）

| | 前端 | 联调 |
|---|---|---|
| M0–M3 | ✅ enums · types · MSW · 认证 · LLM · 用量 | mock |
| M4–M6 | Forge / HITL / 试玩（mock WS） | 待真实 WS |
| M7–M8 | 审批后台 | 待后端 |

---

## License

[MIT](LICENSE)
