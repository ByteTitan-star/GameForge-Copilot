// 平台生成的 Vite 配置（docs/build-pipeline 硬约束③）
// base: './' 为平台级不可覆盖约束：preview token path 下使资源 URL 相对，
// 避免 /assets/* 绝对路径绕过 token 导致 403。LLM 不得修改 base。
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    // 产物体积受 artifact_max_size_mb 约束；source map 默认关闭以减小产物。
    sourcemap: false,
  },
})
