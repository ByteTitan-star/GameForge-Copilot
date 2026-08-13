# 原生 Canvas 2D 引擎方法论

无外部 CDN，全部用浏览器内建 `CanvasRenderingContext2D`。适合实体少、逻辑清晰的轻量游戏。

## 基本结构

- 一个主 `<canvas>`，`ctx = canvas.getContext('2d')`。
- 游戏状态机：`menu / playing / paused / level_complete / game_over / victory`，
  每个状态对应一段 update + render 逻辑，由顶层 `state` 变量分发。
- 主循环用 `requestAnimationFrame`：

```js
let last = performance.now();
function loop(now) {
  const dt = Math.min((now - last) / 1000, 0.05); // 钳制 delta，防卡顿穿模
  last = now;
  if (state === 'playing') update(dt);
  render();
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
```

## 关键纪律

- **delta time 钳制**：`dt` 必须封顶（如 0.05s），否则切后台再回来会一次性大跳。
- **状态重置**：进入 `playing`、重开、切关卡时，重置计时器、输入、实体数组、临时效果，
  不要残留上一局状态。
- **碰撞检测**：AABB 或圆形碰撞自己写，保持函数纯且可测；不要在 render 里改状态。
- **响应式**：`resize` 时按视口重算 canvas 尺寸与逻辑坐标，核心玩法区域保持可见。
- **输入**：键盘（keydown/keyup 维护按键集合）与触控（touchstart/touchmove）同时支持，
  统一映射到「方向/动作」语义再喂给 update。

## 输入与 UI

- 菜单、暂停、结算界面用 DOM 覆盖层或 canvas 内绘制均可，但状态切换函数必须集中在一处。
- HUD（分数/生命）每帧绘制，值变化要立即反映。
