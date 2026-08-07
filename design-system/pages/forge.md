# Forge 设计页 — Page Overrides

> 核心页：多轮对话生成游戏。覆盖 `MASTER.md`。

---

## 风格基调

**浅色游戏工作室（Light Arcade Studio）**

- 工作区 `#E7EBEE`，舞台 `#F4F6F7`，面板 `#F8FAFB`，石墨墨色 `#1D2329`
- 主操作使用珊瑚红 `#FF705C`；钴蓝仅表示运行/对话，成功绿仅表示可试玩，HITL 使用柔和黄色
- 深色仅保留在全局侧栏、主要命令按钮和实际游戏画布中，形成清晰的工作区/试玩区分
- 等宽标签（CHAT / PIPELINE / HITL）继续建立工具感；动效保持克制

## 布局（Scheme A · 对齐 `docs/08-frontend.md`）

沉浸舞台 + 可收起工作台：

| 区域 | 组件 | 职责 |
|---|---|---|
| 主舞台 | `GamePlayer` / 空状态 | 承载创作入口与生成后的沉浸试玩 |
| 底部 Dock | Forge composer | 随时输入新需求或修改意见 |
| 右侧抽屉 | `ChatPanel` / `RunTimeline` / `HitlCard` | 对话、运行进度与策划确认；默认收起，必要时自动展开 |

顶栏：标题、run_id、新游戏、跳转我的游戏；未验证邮箱提示去 Settings。

## 状态色

- 运行中：钴蓝
- 成功构建：绿
- 等待确认：柔和黄色
- 失败：珊瑚红 + 文案

## Mock

- `playMockTimeline` + `buildMockRunTimeline` / `buildMockRunAfterHitl`
- HITL 批准后续跑 art → code → qa → done，右侧自动切到试玩
