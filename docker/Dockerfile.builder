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

# 全局安装固定 pnpm 11.21.0（不用 corepack shim，避免 offline 阶段 corepack 联网拉 pnpm）
RUN npm install -g pnpm@11.21.0 \
    && pnpm -v \
    && mkdir -p /pnpm/store \
    && chmod -R a+rwx /pnpm

ENV PNPM_HOME=/pnpm \
    PATH=/usr/local/bin:/pnpm:$PATH \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

WORKDIR /workspace

# 运行时 uid 由 DockerBuilder 指定（与宿主一致，便于 bind mount 清理）
CMD ["node", "-v"]
