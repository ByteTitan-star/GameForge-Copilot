# GameForge Frontend

React + Vite + TypeScript + Tailwind。契约见 `../docs/10-contract-and-parallel-dev.md`，视觉见 `../design-system/`，工程约定见 [CONVENTIONS.md](./CONVENTIONS.md)。

**联调环境搭建**见仓库根目录 [README.md](../README.md)「联调启动」。

```bash
pnpm install
cp .env.example .env
pnpm dev               # http://127.0.0.1:5173
pnpm test
pnpm smoke:real        # 认证/API 冒烟（需 backend + worker 已起）
```

默认 API：`http://127.0.0.1:8000/api/v1`。
