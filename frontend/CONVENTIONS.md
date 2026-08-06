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
  api/           # 契约枚举、手写 types、client、mock、按域 API
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
- `VITE_USE_MOCK=true`（默认）走 `src/api/mock/`；后端就绪后 `false` + `VITE_API_BASE_URL`。
- OpenAPI 就绪后：`pnpm exec openapi-typescript <url> -o src/api/types.gen.ts`，逐步替换 `types.ts`。

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

## Mock 账号

| 邮箱 | 密码 | 说明 |
|------|------|------|
| demo@gameforge.dev | password123 | 已验证 user |
| unverified@gameforge.dev | password123 | 未验证 |
| admin@gameforge.dev | password123 | admin |
| fail@test.com | * | 登录必失败 |
