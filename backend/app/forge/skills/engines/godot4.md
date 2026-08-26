# Godot 4 原生引擎方法论（P0）

平台已提供固定工程模板（`project.godot`、主场景等），你**只修改** `scenes/main.gd`（必要时可改 `scenes/main.tscn`）。

## 基本结构

- 主脚本继承 `Node2D`，挂在 `scenes/main.tscn` 根节点。
- 游戏状态机：`menu / playing / paused / level_complete / game_over / victory`。
- 用 `_process(delta)` 或 `_physics_process(delta)` 更新逻辑，用 `_draw()` 或子节点渲染。

## 硬性纪律

- **Ready 信号**：`_ready()` 末尾必须 `print("GAMEFORGE_READY")`（平台验收探针，不可删除或改名）。
- **GDScript 4.x** 语法；禁止 `yield`，用 `await`。
- **不要**输出或修改 `project.godot`、导出预设、引擎配置。
- **不要**引用未在模板中声明的外部插件或 Autoload。
- 输入：同时支持键盘（`Input.is_action_pressed`）与触控（`InputEventScreenTouch`）。
- `delta` 应钳制上限（如 `min(delta, 0.05)`）防止卡顿穿模。

## P0 范围

- 2D 玩法为主；用 `CanvasItem` / `Node2D` 绘制与碰撞。
- 不依赖网络、多人、复杂 3D、自定义 Shader 包。
