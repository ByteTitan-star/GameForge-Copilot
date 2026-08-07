# 生成代码工程约定（非玩法约束）

- 单入口：必须产出可直接托管的 `index.html`（可内联 JS/CSS）。
- 无外部网络：禁止 fetch/XHR/WebSocket 外链；资源用 data URL 或内联。
- 无构建依赖：不要假设 npm/webpack；沙箱可能只做透传或简单 shell。
- 自包含：键盘/触控操作写清；页面加载即可玩。
- 安全：不读 cookie / localStorage 跨站数据；不弹恶意窗口。
