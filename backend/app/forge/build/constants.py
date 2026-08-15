"""构建链常量（docs/build-pipeline §7/§10）。"""

# P1 据实形成：Vite+TS 模板构建所需的 lifecycle script 授权（硬约束④）
BUILDER_ALLOWED_BUILDS: dict[str, bool] = {
    "esbuild": True,
}

BUILD_SNAPSHOT_FILES: tuple[str, ...] = (
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "vite.config.ts",
    "tsconfig.json",
    "build-profile.json",
)
