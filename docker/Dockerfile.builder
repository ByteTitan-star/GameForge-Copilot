# gameforge/builder：游戏工程构建镜像（docs/build-pipeline §8）
#
# 职责单一：提供 Node + pnpm + 受控构建工具链，供 Dependency Prepare 与 Build Sandbox 复用。
# 不在此镜像里预装 vite@latest / 业务依赖——构建工具版本必须固定并版本化（硬约束⑤），
# 业务依赖由各工程的 package.json 声明，经 Dependency Prepare 阶段拉取。
#
# 版本：对应 build-profile.json#builder_version = v1。
# 升级 Node/pnpm 时显式发布 gameforge-builder:v2，不在此静默漂移。
# build context = 仓库根目录

FROM node:22-slim

# 固定 pnpm 11（corepack pin 精确版本，不用 latest）。pnpm 11 的非 registry 配置
# （allowBuilds 等）走 pnpm-workspace.yaml，与硬约束④一致。
RUN corepack enable \
    && corepack prepare pnpm@11.21.0 --activate

# pnpm store 默认在用户家目录下；生产通过只读挂载共享宿主 store（§9.1/§9.3），
# 此处仅为无挂载时提供可写默认位置，不预填内容。
ENV PNPM_HOME=/pnpm \
    STORE_DIR=/pnpm/store
RUN mkdir -p "$STORE_DIR" \
    && chown -R node:node /pnpm
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

WORKDIR /workspace

# node:22-slim 已自带 node 用户（uid 1000）。构建期以 node 身份运行，
# 与 Build Sandbox 只读根 + 可写 /workspace 的安全模型配合。
USER node

# 默认不执行任何构建——构建命令由后端按 Dependency Prepare / Build Sandbox
# 两阶段分别覆盖传入（lockfile-only+fetch / offline+frozen build）。
CMD ["node", "-v"]
