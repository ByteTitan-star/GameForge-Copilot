# Design System Master — GameForge-Copilot

> **LOGIC:** 做具体页面时先读 `design-system/pages/[page].md`；有则覆盖本文件，无则严格遵循本文件。  
> **产品主题（不可变）：** Web 端「说清楚规则 → 浏览器里玩 → 改到满意再公开」。一切视觉服务于游戏创作工具，不是通用 AI SaaS、不是 DeFi、不是投资站。

**Stack（与 `docs/08-frontend.md` 对齐）：** React + Vite + TypeScript + Tailwind + shadcn/ui + lucide-react；本地态 Zustand，服务端态 TanStack Query。

---

## 从参考风格学到什么（吸收，不抄袭）

| 参考气质 | 可复用原则 | 禁止照搬 |
|---------|-----------|---------|
| **NovaAI 电影感** | 深色全屏媒体底、磨砂玻璃 chip、稀疏编辑式排版、滚动/视差驱动叙事、白字 + drop-shadow、uppercase mono 微标签 | 文案、品牌、具体视频 URL、咨询卡片人设 |
| **VEX liquid glass** | 全出血视频无压暗、液态玻璃导航/控件、字级交错入场、底部加权 hero、白实心主 CTA + 玻璃次 CTA | 「VEX」品牌、投资站信息架构 |
| **RIVR 轻玻璃** | 浅灰画布 + 圆角媒体舞台、柔和白玻璃浮层、长会话可读性、motion 微动效、切角/遮罩做高级感 | DeFi 文案与指标卡内容 |
| **TOONHUB 轮播** | 角色/资产焦点轮播、背景色随内容变、grain、巨大幽灵字、强焦点层次 | 仅用于「作品展示/发现」类页面，不作全站默认 |

**统一禁令（全站）：** 紫/靛霓虹渐变、奶油纸质背景、emoji 当图标、图标卡片宫格堆砌、占位符当唯一 label。

---

## 页面 × 风格映射

| 表面 | 风格基调 | 密度 | 说明 |
|------|---------|------|------|
| **Landing / 营销** | NovaAI 电影感 + 可选 scroll 媒体 | 疏 | 讲清「对话生成游戏」价值；深色、玻璃、少模块 |
| **Login / Auth** | VEX liquid glass 改造 | 疏 | 全屏氛围底 + 玻璃表单；转化优先；见 `pages/login.md` |
| **Forge 设计页**（对话生成） | RIVR 轻玻璃工作台气质 | 中高 | 浅色/低饱和长会话；左对话右进度；可读 > 炫 |
| **试玩 / 作品发现** | TOONHUB 轮播能量（克制版） | 中 | 突出游戏画面与角色资产 |
| **Setting** | RIVR 轻表面 + 清晰表单 | 中 | 配置 LLM/用量；少动效 |
| **Admin 后台** | RIVR 信息密度 + 中性色 | 高 | 表格/队列优先；玻璃仅作顶栏与浮层 |

文案与路由语义始终围绕：设计会话、生成进度、试玩、发布审批、用量——见 `docs/01-features.md` / `docs/08-frontend.md`。

---

## 双主题 Token

### Dark · Cinematic（Landing / Auth）

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Background | `#0a0a0a` | `--color-background` |
| Foreground | `#FFFFFF` | `--color-foreground` |
| Muted text | `#D1D5DB` (`gray-300`) | `--color-muted-fg` |
| Glass fill | `rgba(255,255,255,0.10–0.15)` | `--glass-fill` |
| Glass border | `rgba(255,255,255,0.15–0.25)` | `--glass-border` |
| Primary CTA | `#FFFFFF` bg / `#000000` text | `--color-cta` |
| Secondary CTA | glass + white text | — |
| Ring / focus | `rgba(255,255,255,0.45)` | `--color-ring` |
| Destructive | `#EF4444` | `--color-destructive` |

### Light · Workspace（Forge / Setting / Admin）

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Canvas | `#F0F0F0` | `--color-canvas` |
| Stage / panel | `#FFFFFF` + soft glass | `--color-stage` |
| Ink | `rgba(30,50,90,0.9)` ≈ slate-ink | `--color-ink` |
| Ink muted | `#5E6470` | `--color-ink-muted` |
| Accent action | `rgba(30,50,90,0.8)` 实心按钮 | `--color-action` |
| Border soft | `rgba(30,50,90,0.1)` | `--color-border-soft` |

游戏主题点缀（两主题共用，克制使用）：成功绿 `#22C55E`（构建成功）、警告琥珀 `#F59E0B`（HITL 等待）、信息青 `#38BDF8`（流式事件）——**不作主品牌色铺满**。

---

## Typography

- **UI 默认：** Inter 400–700 + **Noto Sans SC**（中文）
- **Mono 微标签：** 仍用 `font-mono` class，可映射到 Inter（与参考一致）或系统 mono；uppercase + `tracking-[0.15em]` + `text-[10px–12px]`
- **不要**默认 Russo One / 像素字体 / 酸黄粗野标题（已废弃）
- `antialiased`；选中色 `rgba(255,255,255,0.2)`（深色页）

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet" />
```

---

## Material：Glass / Liquid Glass

**Frost chip（Nova 系）**
- `bg-white/10|15 backdrop-blur-md border border-white/15`
- 左强调徽章：`border-l-2 border-white` + mono uppercase

**Liquid glass（VEX 系，Auth/Landing 导航）**
- 深色半透明 + `backdrop-filter: blur(4px)` + 渐变描边 mask（见实现时全局 `.liquid-glass`）
- 主 CTA：白底黑字 pill/rounded；次 CTA：玻璃描边

**Soft glass（RIVR 系，工作台）**
- `bg-white/30|60 backdrop-blur-xl` 浮在浅灰画布上
- 大圆角舞台 `rounded-[1.5rem–3rem]`

不透明实色大板禁止盖住全出血视频（深色营销页）。

---

## Motion

| 模式 | 用法 | 参数 |
|------|------|------|
| Fade-up reveal | 进视口文案/块 | IO threshold 0.15；`translate-y-8→0` + opacity；700ms ease-out；可 stagger |
| Char stagger | Landing/Auth 主标题 | 每字 ~30ms，单字 500ms；`prefers-reduced-motion` 时整句淡入 |
| Scroll scrub | 仅 Landing 叙事视频 | progress lerp ~0.12；非 loop 自动播放 |
| Loop video | Auth/部分 Hero | muted + playsInline；**无压暗遮罩**（除非对比度不够再局部加） |
| Micro | 按钮 hover | 150–300ms；scale ~1.02；chevron translate-x |
| Workspace | Forge/Admin | 少大动效；面板切换短淡入即可 |

一律尊重 `prefers-reduced-motion: reduce`。

---

## Layout rhythm

- 水平 padding：`px-5 sm:px-8 md:px-12`（营销/认证）或 `px-6 md:px-12 lg:px-16`
- 固定顶栏下内容：`pt-24 sm:pt-28`
- 间距阶梯：4 / 8 / 16 / 24 / 32 / 48 / 64
- 图标：lucide-react，线性一致；触控目标 ≥ 44px

---

## 无障碍与表单（全站）

- 每个 input 有可见 label（禁止 placeholder-only）
- 错误：`role="alert"` + 文案，不只靠颜色
- 提交中禁用按钮 + loading
- `focus-visible` ring 可见
- 可点击元素 `cursor-pointer`

---

## Pre-Delivery Checklist

- [ ] 主题仍是「小游戏开发 Web」，无错用金融/咨询话术
- [ ] 页面风格符合上表映射（或有 pages 覆盖说明）
- [ ] 无紫霓虹 / 无奶油纸 / 无 emoji 图标
- [ ] 深色页文字对比可读；玻璃未导致正文糊掉
- [ ] 动效可被 reduced-motion 关掉
- [ ] 中英文混排：Noto Sans SC 兜底
- [ ] 响应式：375 / 768 / 1024 / 1440
