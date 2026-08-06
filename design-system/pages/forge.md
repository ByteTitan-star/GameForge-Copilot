# Forge 设计页 — Page Overrides

> 核心页：多轮对话生成游戏。覆盖 `MASTER.md`。

---

## 风格基调

**深色命令台（Command Console）**

- 画布 `#0b0d10`，面板 `#12151a`，细白边 `white/8`
- 强调色：信息青 / 成功绿 / HITL 琥珀；避免紫霓虹与奶油纸风
- 等宽标签标签（CHAT / PIPELINE / HITL）建立「控制台」语感
- 动效克制：消息追加、阶段 chip、事件卡淡入即可

## 布局（Scheme A · 对齐 `docs/08-frontend.md`）

三栏工作台：

| 栏 | 组件 | 职责 |
|---|---|---|
| 左 | `ChatPanel` | 需求多轮对话 + 发送 |
| 中 | `RunTimeline` + `HitlCard` | 阶段 chip + 事件时间线；`hitl_wait` 时插入确认卡 |
| 右 | `ForgeSidePanel` | 事件日志 / 试玩（`GamePlayer` sandbox）切换 |

顶栏：标题、run_id、新游戏、跳转我的游戏；未验证邮箱提示去 Settings。

## 状态色

- 运行中：青（cyan / teal）
- 成功构建：绿
- 等待确认：琥珀
- 失败：红 + 文案

## Mock

- `playMockTimeline` + `buildMockRunTimeline` / `buildMockRunAfterHitl`
- HITL 批准后续跑 art → code → qa → done，右侧自动切到试玩
