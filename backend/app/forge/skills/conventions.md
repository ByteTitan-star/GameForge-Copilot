# 生成代码工程约定（非玩法约束）

- 单入口：必须产出可直接托管的 `index.html`。
- 脚本来源：游戏逻辑 JS/CSS 一律内联；仅允许通过 `<script src>` 引用白名单 CDN
  上的游戏引擎 UMD 包（如 Phaser/PixiJS）。引擎脚本不属于"外部依赖"，但必须
  在加载失败时给出程序化回退，且不阻塞游戏启动。
- 无外部网络：禁止 fetch/XHR/WebSocket 业务外链；除上述引擎与字体 CDN 外，
  其余资源用 data URL 或内联。
- 无构建依赖：不要假设 npm/webpack/vite；不写 import 语句、不用 ES 模块，
  沙箱只做透传或简单 shell。
- 自包含：键盘/触控操作写清；页面加载即可玩。
- 安全：不读 cookie / localStorage 跨站数据；不弹恶意窗口。
