# Phaser 3 引擎方法论（CDN UMD）

通过白名单 CDN 引入 Phaser UMD：必须使用策划稿 `engine.version` 对应的精确 URL，
**不得更改版本号或路径**。CDN 脚本加载失败时，要有程序化回退（降级提示或纯 Canvas 兜底），
不阻塞页面。

## 引入与启动

```html
<script src="https://cdn.jsdelivr.net/npm/phaser@<VERSION>/dist/phaser.min.js"></script>
<script>
  // 加载失败回退
  if (typeof Phaser === 'undefined') { /* 降级：显示提示或转 canvas 实现 */ }
</script>
```

启动配置用 `type: Phaser.AUTO`，允许在无 WebGL 环境（含 headless 试玩）自动降级 Canvas：

```js
const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: 800, height: 600,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: [BootScene, MenuScene, PlayScene, ...],
  physics: { default: 'arcade', arcade: { debug: false } },
});
```

## Scene 生命周期

- 每个 Scene 继承 `Phaser.Scene`，实现 `preload / create / update`。
- **preload**：仅 `this.load.image/spritesheet/audio`，不写业务逻辑。
- **create**：构建本场景对象、绑定输入、注册碰撞。
- **update(time, deltaMs)**：每帧逻辑，`deltaMs` 已由引擎提供，无需自己算 RAF。
- 场景切换用 `this.scene.start('PlayScene')`，对应策划稿 `game_states` 的 6 个状态。

## 状态机映射

- `menu / playing / paused / level_complete / game_over / victory` 各自一个 Scene，
  或在 PlayScene 内用子状态管理；状态 id 与策划稿保持一致。
- 重开/重进关卡：新开 Scene 实例即天然重置；若用子状态，手动清实体组与计时器。

## 物理与碰撞

默认用 **Arcade Physics**（平台跳跃、弹道、简单碰撞）：

- `this.physics.add.collider` / `overlap`，回调里改状态/加分。
- 禁止在物理回调里做耗时操作或销毁正在迭代的对象，用事件队列延迟处理。

仅当玩法需要刚体约束、悬挂、重心（如越野车、铰链）时，改用 **Phaser 内置 Matter**，不要另引 npm `matter-js`：

```js
physics: { default: 'matter', matter: { gravity: { y: 1 }, debug: false } }
```

合法 API（3.80）：`this.matter.add.image`、`this.matter.add.sprite`、`this.matter.add.rectangle`、`this.matter.add.circle`、`this.matter.add.constraint`、`this.matter.world.setBounds`。
车辆用 chassis rectangle + 两轮 circle + 两个 constraint；读坐标前确认 body 已创建（`body.position.x` 或 sprite.x）。

禁止：`this.matter.add.group()`（不存在）；显示分组用 `this.add.group()`。禁止把 Arcade 的 `this.physics.add.collider` 用在 Matter 场景。

## 纪律

- 不要手写 `requestAnimationFrame`——Phaser 自己跑主循环；再套一层会双倍帧率。
- 不要混用裸 Canvas API 改 Phaser 场景内容，统一走 Sprite/Graphics/Image。
- 资源加载用 preload；运行期动态加载要监听 complete 事件再使用。
