# Vite + TypeScript 固定模板（P1 验证用）

> 对应 `docs/build-pipeline.md` P1：验证构建基础设施，LLM 暂不参与。

本目录是一份**平台侧固定的 Vite+TS 工程**，用于在 P1 验证整条构建链：

```
pnpm install --lockfile-only   # 在线解析，产出 pnpm-lock.yaml（Dependency Prepare）
pnpm fetch                      # 在线填充 shared store（Dependency Prepare）
# —— 切断网络 ——
pnpm install --offline --frozen-lockfile --frozen-store   # Build Sandbox，只读 store
pnpm build                      # 产出 dist/index.html
```

## 文件职责

| 文件 | 谁负责 | 说明 |
|---|---|---|
| `package.json` | 平台 | 固定版本，无 `latest`/`*`/`^` |
| `pnpm-workspace.yaml` | 平台 | `allowBuilds`（硬约束④）；业务依赖默认无 build 权限 |
| `vite.config.ts` | 平台 | `base: './'`（硬约束③），平台级不可覆盖 |
| `tsconfig.json` | 平台 | 严格模式 |
| `index.html` | 平台 | Vite 入口 |
| `src/main.ts` | 平台（P1）/ LLM（P2+） | P1 只渲染一个 Canvas 验证链路；P2 起此处由 LLM 生成的源码替换 |

## 三层产物映射（§12）

P2 起，此模板对应 `build/` 层（平台决定）；LLM 产出的 `src/*.ts` 对应 `source/` 层；构建产物对应 `dist/` 层。

## 验证步骤

```bash
# 1. 构建 builder 镜像
docker build -f docker/Dockerfile.builder -t gameforge-builder:v1 .

# 2. 联网阶段：生成 lockfile + 填充 store（host 挂载 store 目录以复用）
docker run --rm \
  -v "$(pwd)/docker/templates/vite-ts:/workspace" \
  -v "$(pwd)/.pnpm-store:/pnpm/store" \
  --network host \
  gameforge-builder:v1 \
  sh -c "pnpm config set store-dir /pnpm/store && \
         pnpm install --lockfile-only && \
         pnpm fetch"

# 3. 断网阶段：offline + frozen build
docker run --rm \
  -v "$(pwd)/docker/templates/vite-ts:/workspace" \
  -v "$(pwd)/.pnpm-store:/pnpm/store:ro" \
  --network none \
  gameforge-builder:v1 \
  sh -c "pnpm config set store-dir /pnpm/store && \
         pnpm install --offline --frozen-lockfile --frozen-store && \
         pnpm build"

# 4. 验收：dist/index.html 存在，且资源为相对路径 ./assets/...
ls docker/templates/vite-ts/dist/index.html
```

> 步骤 2 的 `--network host` 与步骤 3 的 `--network none` 是 P1 手动模拟"Dependency Prepare 联网 / Build Sandbox 断网"两阶段；P2 起由后端 `DependencyPreparer` 与 `DockerSandbox` 自动编排。
