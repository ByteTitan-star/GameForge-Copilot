# Frontend 工程约定（GameForge）

面向后续后端联调与多人协作。视觉规范见 `../design-system/`。

## 技术栈

- React 19 + Vite + TypeScript（strict）
- Tailwind CSS v4（`@tailwindcss/vite`）
- React Router、TanStack Query、Zustand
- 图标：`lucide-react`
- 包管理：pnpm

## 目录

```
src/
  api/           # 契约枚举、types、client、按域 API
  components/    # ui / layout / auth / game
  pages/         # 路由页面
  stores/        # 本地态
  i18n/          # zh/en 文案
  lib/           # cn、env
  routes.tsx
```

## 与后端契约

- 字段 **snake_case**，与 `docs/10-contract-and-parallel-dev.md` 一致。
- 枚举只改 `src/api/enums.ts`。
- 前端只连真实 API：`VITE_API_BASE_URL`（默认 `http://127.0.0.1:8000/api/v1`）。
- OpenAPI 就绪后：`pnpm gen:api`，逐步对齐 `types.gen.ts`。

## UI 规范

- 认证 / Landing：深色 + liquid-glass（`design-system/pages/login.md` / `landing.md`）
- Forge / Settings / Admin：浅色工作台（`forge.md` / `admin.md`）
- 试玩：`GamePlayer` 必须 `sandbox="allow-scripts"`，不加 `allow-same-origin`
- 表单：可见 label、错误 `role="alert"`、提交 loading

## 脚本

```bash
pnpm dev
pnpm build
pnpm lint
```

## 联调验收账号

认证走真实 API：自行注册，在 Worker 终端 `[dev-email]` 取验证链接。

若后端已 seed 测试账号，见 `backend` 测试 fixture 或问后端同学；前端不再内置 Mock 账号表。
