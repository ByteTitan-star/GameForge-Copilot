# PixiJS 引擎方法论（CDN UMD）

通过白名单 CDN 引入 PixiJS UMD：必须使用策划稿 `engine.version` 对应的精确 URL，
**不得更改版本号或路径**。加载失败要有程序化回退，不阻塞页面。

PixiJS 只负责高性能 2D 渲染（WebGL，无 GPU 时降级 Canvas），**游戏循环、状态机、碰撞、
输入逻辑由你自己实现**——它不像 Phaser 自带物理/场景框架。

## 引入与启动

```html
<script src="https://cdn.jsdelivr.net/npm/pixi.js@<VERSION>/dist/pixi.min.js"></script>
<script>
  if (typeof PIXI === 'undefined') { /* 降级 */ }
  const app = new PIXI.Application({
    width: 800, height: 600,
    background: '#111',
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });
  document.body.appendChild(app.view);
</script>
```

## 主循环

用 `app.ticker.add((delta) => { ... })`，`delta` 是相对上一帧的倍数（1 = 60fps）。
**不要再用 `requestAnimationFrame`**，否则与 Ticker 重复驱动。

```js
app.ticker.add((delta) => {
  if (state === 'playing') update(delta);
  render(); // 一般直接由容器树渲染，仅同步数据到 sprite 属性即可
});
```

## 状态与对象组织

- 用 `PIXI.Container` 分层：背景层、实体层、特效层、UI 层，便于整体清空与重排。
- 状态机 `menu/playing/paused/level_complete/game_over/victory` 自己维护，
  切换时清空对应容器、重置计数器与输入。
- sprite 复用：频繁创建销毁的对象用对象池，避免 GC 抖动。

## 纪律

- 碰撞/物理自己写（AABB/圆形），保持与渲染分离。
- 输入：监听 `app.view` 或 window 的 keydown/touch，映射到统一动作语义。
- 响应式：监听 resize，调用 `app.renderer.resize(w, h)` 并重算逻辑坐标。
- 切场景/重开时停掉对应 Ticker 回调或重置容器，避免上一局残留继续渲染。
