# GameForge Frontend

React + Vite + TypeScript + Tailwind。契约见 `../docs/10-contract-and-parallel-dev.md`，视觉见 `../design-system/`，工程约定见 [CONVENTIONS.md](./CONVENTIONS.md)。

**完整前后端从零启动**见仓库根目录 [README.md](../README.md)「从零启动」。

```bash
pnpm install
cp .env.example .env   # VITE_API_BASE_URL 指向真实后端
pnpm dev               # http://127.0.0.1:5173
pnpm test
pnpm build
pnpm smoke:real        # API 冒烟（需 backend 已起）
```

默认连接 `http://127.0.0.1:8000/api/v1`；本地开发需同时启动 Postgres、Redis、API 与 Worker（见根 README 路径 B）。
