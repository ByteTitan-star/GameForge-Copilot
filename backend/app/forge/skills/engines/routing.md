# 引擎选型指南（注入策划阶段）

为游戏选择技术栈时，按玩法复杂度匹配。**Web 路线**（单 HTML / Vite 浏览器游戏）与 **Native 路线**（Godot 工程，需 `NATIVE_ENGINE_ENABLED`）互斥，同一份设计稿只选一个 `engine.id`。

## Web 受控选项

受控选项：`canvas`、`phaser3`、`pixijs`。

## canvas —— 原生 Canvas 2D

适用：网格/回合制/轻量街机。贪吃蛇、2048、俄罗斯方块、打砖块、井字棋、点击放置。
判断信号：实体少、无物理、画面可每帧整屏重绘、状态切换简单。

## phaser3 —— Phaser 3（CDN UMD）

适用：2D 动作/街机/平台/物理碰撞。塔防、横版跳跃、射击、弹幕、休闲动作。
判断信号：需要碰撞检测、精灵动画、多场景、音效、物理弹道——这些手写极易出错，Phaser 内建。
物理默认 Arcade；仅刚体约束/悬挂/重心才启用内置 Matter（`physics.default: 'matter'`），不要另引 npm matter-js，禁止 `this.matter.add.group()`。

## pixijs —— PixiJS（CDN UMD）

适用：高性能 2D 渲染、大量精灵、粒子、WebGL 特效。渲染压力大但不需要完整物理引擎的场景。
判断信号：同屏数百以上动态对象、强视觉特效、且玩法逻辑自己掌控（PixiJS 只管渲染）。

## godot4 —— Godot 4 Native（平台模板 + GDScript）

**仅当平台开启 Native Engine 时可选。** 适用：需要真实 Godot 工程、headless 引擎验收、
2D 原生玩法验证；不适合浏览器即开即玩分发。
判断信号：策划明确要求 Godot/GDScript、或需要引擎级 import/run 诊断闭环。
约束：`build_routing.build` 应为 `none`；平台提供 `project.godot` 模板，Agent 只填 `scenes/` 脚本；
`engine.version` 填 `4.3`（与平台钉死版本一致）。

## 选择原则

1. 默认倾向 `canvas`；只有当玩法明确需要碰撞/物理/多场景/精灵动画时才上 `phaser3`。
2. `pixijs` 仅在渲染是主要瓶颈、且不需要完整游戏框架时选用；多数情况 `phaser3` 更省事。
3. `godot4` 仅在 Native Engine 已开启、且目标为 Godot 工程验收时使用；**不要**与 Web 引擎混选。
4. 选定后必须在 `engine.version` 填写与引擎完全一致的版本号，rationale 写清为什么选它。
5. 同一份游戏只选一个引擎，不要混用。
