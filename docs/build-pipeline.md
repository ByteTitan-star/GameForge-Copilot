# 游戏生成构建链（Build Pipeline）设计规格

> 状态：**评审定稿（frozen）**，冻结后即进入 P1
> 作者：wangxin
> 关联代码：`backend/app/forge/`、`backend/app/sandbox/`、`backend/app/hosting/`、`docker/`
> 工具链基线：pnpm 11、Vite（`base: './'` 相对部署）

---

## 0. 评审定稿与前一稿的差异

本稿相对评审讨论稿，按已拍板的决策**彻底统一**了概念，删除以下残留：

| 残留概念 | 处理 |
|---|---|
| Capability（`physics-2d`/`audio`/`tween` 抽象） | **第一阶段删除**，只做 dependency catalog |
| `source.tar.zst` / 压缩 / CAS | **删除**，Source 多文件直接存，不压缩不去重 |
| Build Sandbox 经 egress proxy 联网装依赖 | **删除**，改为 Dependency Prepare 联网 + Build Sandbox `NetworkMode=none` |
| `pnpm install --ignore-scripts` + `.npmrc` 补洞 | **删除**，改用 pnpm 11 `pnpm-workspace.yaml#allowBuilds` 显式授权 |
| `catalog version == builder version` 强绑定 | **改为独立**，三个版本各自独立演进 |
| 预览鉴权 = 单文件 presigned URL | **删除**，改 Artifact Path Preview Token（整树共享授权上下文） |
| 仅区分 Source / Runtime 两层 Artifact | **改为三层**：Source / Build Snapshot / Runtime |

新增并固化为**四个不可绕过的硬约束**（§10）与一个**三层产物结构**（§12）。

---

## 1. 背景与目标

### 1.1 现状

当前游戏产物**强制为单个自包含 `index.html`**，约束来自四层（均带代码证据）：

* 提示词输出契约：`prompts.py:326`「只输出完整 HTML 源码，首字符必须是 `<!DOCTYPE html>`，以 `</html>` 结束」；`_CODE_COMMON`（`prompts.py:55`）「只生成一个自包含 index.html，JS/CSS 一律内联」。
* 代码节点：`graph.py:794` `execute(source={"index.html": html})`，source 只有一个 key。
* 沙箱：`docker.py:64` 无 `build_cmd` 时仅 `test -f /workspace/index.html`；`graph.py:794` 调用根本没传 `build_cmd`。**当前 HTML 不在沙箱里构建/执行，沙箱只做写盘 + 文件存在性检查。**
* 试玩：`playtest.py` 默认走 `_static_playtest`（`playtest.py:203`），纯 Python 正则扫描，不执行 JS；仅 `PLAYTEST_USE_PLAYWRIGHT=1` 时用真浏览器。
* 托管：`hosting/local.py:59`、`hosting/routes.py:43` 固定读写单个 `index.html`。

已支持三个 CDN-UMD 引擎 `canvas` / `phaser3` / `pixijs`（`engine_router.py:19`）。**框架层面已具备中等能力，真正瓶颈不是渲染框架，而是：游戏必须压成单 HTML，且没有 npm / TypeScript / Vite 标准前端构建链。** 这限制了 LLM 使用 npm 生态（物理/动画/声音/3D 库）、代码模块化、TypeScript、代码分包，以及 React 等 UI 框架。

### 1.2 目标

增加一种新的游戏交付模式：

> **LLM 生成多文件源码工程，由受控构建环境构建为静态 `dist/`，最终仅部署浏览器真正需要的 HTML / JS / CSS / assets。**

具体目标：支持 npm 生态（matter-js / howler / gsap / three / phaser / pixi.js / react 等）、多文件工程、TypeScript、Vite 构建、React 等 UI 框架；保留现有 single-html 轻量路线；构建失败可自动修复并最终降级 single-html；**`node_modules` 不进入游戏产物，不进入对象存储**。

### 1.3 非目标（当前规模：几十到几百个游戏）

本阶段明确不做：不要求所有游戏用 React/Vite；不允许 LLM 任意安装 npm 包或自由控制 `package.json`；不把 Node.js 作为游戏运行环境；不保存 `node_modules`；不实现 K8s 级独立 Build Farm、分布式依赖缓存、Artifact CAS 与跨游戏文件去重。

**优先级：简单、稳定、安全、可维护**，而非提前建设百万级游戏需要的基础设施。

---

## 2. 为什么不采用原方案（决策依据）

原方案核心：`LLM 生成 package.json → Build Sandbox → pnpm install（经 egress proxy 访问 npm）→ pnpm build`。技术上能跑，但不作为推荐方案，逐条否决：

### 2.1 不共享 `node_modules`，改共享 pnpm Store

`node_modules` 是项目级依赖视图，受 package 版本、依赖树、peer/optional deps、包管理器版本、Node 版本、lockfile、hoisting 策略影响，多游戏共用 `/shared/node_modules` 必然依赖污染。**共享的是 pnpm Store（content-addressed），不是 node_modules**：每次构建仍拥有自己的临时 `/workspace/node_modules`，但从统一 Store 链接/复用，无需重复完整下载；构建结束 `/workspace` 整体删除。

### 2.2 `node_modules` 不属于游戏产物

React/Phaser/Three 经 Vite 构建后，浏览器运行时只需 `dist/index.html` + `assets/*`，不读 `node_modules`。即便构建期 `node_modules=100MB`、最终 `dist=1~10MB` 也完全正常。**Node.js、pnpm、node_modules 都属于 Build Environment，不属于 Game Artifact。**

### 2.3 不让 LLM 自由生成 `package.json`

LLM 可能生成 `some-random-package: latest`，造成包名幻觉、typo package、不存在版本、版本漂移、安装脚本风险、供应链风险、无法复现、修复时顺手改构建环境。**LLM 只声明需要什么依赖，不直接生成完整 `package.json`**；`package.json`、Vite 配置、构建脚本由平台生成。

### 2.4 不让 Build Sandbox 直接联网

egress proxy 比完全开放安全，但 LLM 生成代码与网络访问能力处于同一执行环境，增加 SSRF/数据外泄防护、proxy 配置、npm 安装脚本联网、网络策略测试的成本。当前规模没必要为"构建时现拉依赖"牺牲安全边界。**采用：下载依赖（有限联网）与执行 LLM 代码（断网）分两个阶段。**

### 2.5 不全局 `vite@latest`，固定 Builder Toolchain

全局 `vite@latest` 会让构建工具版本与项目脱离，同一份源码不同时间构建产生不同结果。**采用固定并版本化的 Builder Toolchain**（`gameforge-builder:v1`），升级时显式发布 `v2`，而非静默漂移。

### 2.6 不用 `pnpm install --prod`，用 `--offline --frozen-lockfile`

前端构建需要 vite/typescript/`@vitejs/plugin-react` 等 **devDependencies**，`--prod` 会跳过它们导致构建失败。正确模型：`pnpm install --offline --frozen-lockfile` + `pnpm build`，仅采集 `dist/`，构建后 workspace 删除，devDependencies 磁盘占用不影响最终产物。

### 2.7 不只签名 `index.html`，改 Artifact Path Preview Token

presigned 单文件假设 `<script src="assets/index.js">` 自动继承签名，**该假设不成立**——浏览器对子资源是独立请求，不携带 index.html 的签名参数。多文件 artifact 不应仅对单文件 presign。**采用整个 Artifact Path 统一 preview token 鉴权。**

---

## 3. 核心设计原则

* **原则一：Build 与 Runtime 完全分离。** 构建期有 Node/pnpm/Vite/node_modules；运行时只是静态 Web Artifact，无 Node。
* **原则二：Source / Dependency Cache / Runtime Artifact 三者分离。** 生命周期不同，不混在一起。
* **原则三：LLM 控制业务源码，不控制构建基础设施。** LLM 决定游戏逻辑/组件/Scene/CSS/资源使用；不决定 Node/pnpm/Vite 版本、registry、任意 npm package、安装脚本、构建命令。
* **原则四：Build Sandbox 默认无网络。** `NetworkMode=none`，依赖下载发生在单独受控阶段。
* **原则五：最终只发布 `dist/`。** 对象存储与 CDN 永远只关心 `dist/`，未来换 bundler（Rspack/esbuild）Hosting 层无需变化。

---

## 4. 目标架构

```text
用户需求
   │
   ▼
┌────────────────────────────┐
│ Plan Node                  │   routing: build / renderer / ui / dependencies
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│ Code Node                  │   生成业务源码；不生成 package.json；不决定 npm 版本
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│ Build Manifest Generator   │   纯代码、不联网；生成 package.json / vite.config.ts /
│ (平台侧)                    │   tsconfig.json / pnpm-workspace.yaml / build-profile.json
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│ Dependency Prepare         │   有受控 npm 网络访问；pnpm install --lockfile-only
│ (平台侧、可独立、幂等)        │   → pnpm fetch；产出 pnpm-lock.yaml + 填充 shared store
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│ Build Sandbox              │   NetworkMode=none；pnpm install --offline --frozen-lockfile
│ (执行 LLM 代码)              │   → pnpm build；采集 dist/
└─────────────┬──────────────┘
       ┌──────┴──────┐
     success        failed
       │             │
       │          Repair Agent (仅改 source/dependencies，不改构建基础设施)
       │             │ retry ≤ build_max_retries
       ▼             ▼
      dist/        最终降级 single-html 重生成
       │
       ├────────► Playtest（dist/ 临时静态服务器 + Playwright）
       └────────► Artifact Store（source/ + build/ + dist/）
```

---

## 5. 工程形态 Routing Schema

**三个正交维度**，不再把 `vite-react` 当 engine：

```json
{
  "build": "vite",
  "renderer": "phaser3",
  "ui": "react",
  "dependencies": ["matter-js", "howler"]
}
```

| 维度 | 取值 | 说明 |
|---|---|---|
| `build` | `none` / `vite` | `none` = single-html 老路；`vite` = 多文件工程 |
| `renderer` | `canvas` / `phaser3` / `pixijs`（`threejs` 后续开启） | 渲染引擎，决定平台自动注入的基础依赖 |
| `ui` | `none` / `react` | UI 框架，`react` 平台自动注入 react + react-dom |
| `dependencies` | catalog 允许的包名数组 | **Agent 只选额外依赖**，基础依赖由 `renderer`/`ui` 自动补齐 |

**基础依赖自动补齐（平台决定，Agent 不写）：**

```text
renderer=phaser3  → 平台自动加 phaser
renderer=pixijs   → 平台自动加 pixi.js
ui=react          → 平台自动加 react + react-dom
dependencies      → Agent 仅从 catalog 选额外依赖，如 ["matter-js"]
```

即 Agent 写 `["matter-js"]`，平台补齐后实际 `package.json` 依赖为 `phaser + matter-js`。**第一阶段不做 capability 抽象**（`physics-2d → matter-js` 这类映射），只做 dependency catalog 校验；capability 留待真正需要时再做。

### 路由建议

* **single-html**（`build=none`）：贪吃蛇、2048、井字棋、简单 Canvas/小型回合制/非复杂 UI 游戏。例：`{"build":"none","renderer":"canvas","ui":"none"}`。
* **vite**（`build=vite`）：需要 npm 包、多 Scene、代码较多、TypeScript、React UI、复杂状态管理、物理引擎、大量模块化代码。例：`{"build":"vite","renderer":"phaser3","ui":"none","dependencies":["matter-js","howler"]}`。

---

## 6. LLM 输出契约（结构化 JSON）

### 6.1 single-html（兼容老逻辑）

```json
{
  "format": "single-html",
  "renderer": "canvas",
  "files": { "index.html": "..." }
}
```

### 6.2 vite 工程

```json
{
  "format": "project",
  "build": "vite",
  "renderer": "phaser3",
  "ui": "none",
  "dependencies": ["matter-js", "howler"],
  "files": {
    "src/main.ts": "...",
    "src/Game.ts": "...",
    "src/scenes/GameScene.ts": "...",
    "src/style.css": "..."
  }
}
```

**LLM 不输出**（由平台生成）：`package.json`、`pnpm-lock.yaml`、`pnpm-workspace.yaml`、`vite.config.ts`、`tsconfig.json`。LLM 输出的 `dependencies` 必须全部在 catalog 内，否则校验失败回 Repair。

---

## 7. Dependency Catalog

后端维护允许使用的 package allowlist（固定版本，由平台控制）：

```python
DEPENDENCY_CATALOG = {
    "phaser":   {"version": "3.x.x 精确版本"},
    "pixi.js":  {"version": "精确版本"},
    "react":    {"version": "精确版本"},
    "react-dom":{"version": "精确版本"},
    "matter-js":{"version": "精确版本"},
    "howler":   {"version": "精确版本"},
    "gsap":     {"version": "精确版本"},
}
```

第一阶段只开放少量经验证的纯 JS 依赖，避免 native addon / node-gyp / 任意二进制下载 / 复杂 postinstall（见 §11）。`renderer`/`ui` 自动注入的依赖同样受 catalog 版本约束。

---

## 8. Builder Toolchain 与版本（三个版本各自独立）

### 8.1 镜像

新增独立镜像 `docker/Dockerfile.builder`（不把构建职责塞进 Python sandbox 镜像）：

```dockerfile
FROM node:<固定版本>-slim
RUN corepack enable && corepack prepare pnpm@11 -activate
WORKDIR /workspace
USER node
```

镜像版本固定为 `gameforge-builder:v1`，运行时不漂移 `pnpm@latest`/`vite@latest`。

### 8.2 三个独立版本

**不把 `catalog version` 绑死 `builder version`**（升级 matter-js 小版本不必重建 builder 镜像）。三者独立：

```json
{
  "builder_version": "v1",
  "dependency_catalog_version": "2026-08-14.1",
  "template_version": "v1"
}
```

### 8.3 Build Profile 概念

三者统一聚合为 Build Profile，写入 `build/build-profile.json`：

```text
Build Profile
├── builder image        （Node、pnpm）
├── dependency catalog   （Phaser、React、Matter 版本）
└── template             （Vite、tsconfig、workspace config）
```

### 8.4 重建的依赖事实来源 = lockfile

**一旦 `pnpm-lock.yaml` 已生成并保存，重建时 dependency catalog 不再参与 dependency resolution**，直接用原 `package.json` + `pnpm-lock.yaml` + `pnpm-workspace.yaml` 重建——这才是真正意义上的 build snapshot。Build Sandbox 可进一步用 `--frozen-store`（见 §10 硬约束②）。

---

## 9. Dependency Prepare 与 Shared pnpm Store

不建设独立 Dependency Resolver 微服务，在 Build Pipeline 中加一个受控步骤即可。

### 9.1 Shared pnpm Store

宿主机维护 `/var/cache/gameforge/pnpm-store`，所有游戏构建复用。重复 package 无需重新完整下载。

### 9.2 Dependency Prepare（联网阶段）

```text
可信程度：平台代码
网络：允许 npm registry
执行 LLM 游戏代码：否
```

该阶段**只**负责：依据平台生成的 package manifest 完成依赖解析与获取，写入 shared store；不执行游戏代码、不执行构建。

**实现拆为两步（阶段边界由 pnpm 官方命令天然划分）：**

```bash
pnpm install --lockfile-only   # 只更新 lockfile/manifest，不创建 node_modules
pnpm fetch                     # 从 lockfile 获取依赖填充 store（忽略 manifest）
```

* `pnpm install --lockfile-only`：官方定义只更新 lockfile/manifest、不创建 `node_modules`，承担在线依赖解析。
* `pnpm fetch`：官方定义从 lockfile 获取依赖填充 store，忽略 package manifest，承担离线 store 填充。

于是完整生命周期为：`package manifest → online resolution(lockfile) → fetch store → offline install`，Build Sandbox 不承担依赖解析。

### 9.3 Build Sandbox（断网阶段）

```text
NetworkMode: none
shared pnpm store 以只读方式挂载
```

执行：

```bash
pnpm install --offline --frozen-lockfile --frozen-store
pnpm build
```

即使生成代码含 `fetch("https://evil.com")`，构建环境也无外网。

### 9.4 Store 写入隔离

Dependency Prepare **独占写入** shared store；Build Sandbox 只读挂载，杜绝 LLM 代码污染全局 store。

---

## 10. 四个硬约束（不可绕过，实现与评审必查）

### 硬约束 ① — Lockfile 在线生成，归属 Dependency Prepare

```text
Manifest Generator（纯代码、不联网）
  → 生成 package.json / vite.config.ts / tsconfig.json / pnpm-workspace.yaml
Dependency Prepare（联网）
  → pnpm install --lockfile-only   # 产出 pnpm-lock.yaml
  → pnpm fetch                      # 填充 shared store
Build Sandbox（断网）
  → 仅消费现成 lockfile + 只读 store
```

**Build Sandbox 永不承担依赖解析。** Manifest Generator 与 lockfile 生成的边界严格分离，避免 Build Sandbox 联网。

### 硬约束 ② — Build Sandbox 离线 + frozen

```text
NetworkMode = none
pnpm install --offline --frozen-lockfile --frozen-store
```

`--offline --frozen-lockfile --frozen-store` 是 pnpm 官方为"完整 store + 不允许修改 store/lockfile"场景给出的组合。`--frozen-store` 保证 store 在构建期不被改动。

**版本一致性前提**：catalog 版本演进时，已保存的 `pnpm-lock.yaml` 是重建的唯一事实来源（§8.4），不因 catalog 升级而错位。

### 硬约束 ③ — Vite `base: './'`，平台级不可覆盖

平台生成的 `vite.config.ts` 必须固定：

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  base: './',           // 平台级约束，LLM 不允许修改 base
  build: { outDir: 'dist' },
})
```

**理由**：preview token path 为 `/preview/{token}/{game}/{version}/`，Vite 默认 `base='/'` 会把资源写成绝对路径 `/assets/index.js`，浏览器请求 `/assets/...` 丢失 token → 403。`base: './'` 使产物所有 URL 相对各自文件（Vite 官方："make all generated URLs to be relative to each other"），`/preview/TOKEN/GAME/VERSION/index.html` 里的 `./assets/index.js` 自然解析为 `/preview/TOKEN/GAME/VERSION/assets/index.js`，token 不丢。

**两个连带约束（写入提示词）：**

1. **运行时 URL 必须相对**：代码中拼接 URL 一律用 `import.meta.env.BASE_URL`（相对 base 下该变量在构建时静态替换为相对值）；禁止任何绝对路径写法（`fetch('/api/...')`、`new URL('/x', location)` 等会绕过 token 路径）。Vite 相对 base 依赖 `import.meta`（现代浏览器均满足）。
2. **禁止 Browser History 路由**：静态 Game Artifact 无服务端 SPA fallback；React 游戏若需页面路由，必须用 hash-based routing。

### 硬约束 ④ — Lifecycle scripts 由 pnpm 11 `allowBuilds` 显式授权

**不使用** `pnpm install --ignore-scripts` + `.npmrc` 补洞。pnpm 11 的安全模型改为：在 `pnpm-workspace.yaml`（非 `.npmrc`，pnpm 11 的非 registry 配置进 workspace 文件）显式授权允许执行 build scripts 的包：

```yaml
# pnpm-workspace.yaml（平台生成，业务依赖默认无 build 权限）
allowBuilds:
  esbuild: true
  # 其他 builder toolchain 实际需要的包，P1 固定模板跑通后据实补全
```

**官方行为**（已核对 pnpm 11 settings/build）：

* `allowBuilds` 为对象/map 形式，key 是 package matcher，value 布尔；**支持版本范围限定**：`nx@21.6.4 || 21.6.5: true`、`esbuild: false`。
* 未列入 `allowBuilds` 的包默认 disallowed（`strictDepBuilds` 默认 true 时报错）。
* 取代了 v10 的 `onlyBuiltDependencies` / `neverBuiltDependencies` / `ignoredBuiltDependencies`（这些已移除）。

**平台策略**：dependency catalog 中的业务依赖默认不拥有 build script 权限；`allowBuilds` 仅授权 Builder Toolchain 实际需要的包（如 esbuild/swc 类 native 构建工具，否则 Vite 跑不起来）。**P1 不凭感觉写死**，先跑固定 Vite+TS 模板，观察真正需要 build script 的包，据实形成 `BUILDER_ALLOWED_BUILDS`，必要时限定版本。

---

## 11. install scripts 与供应链

与硬约束 ④ 配套：依赖安装阶段默认禁止不必要的 package lifecycle scripts，需要 build script 的包必须进 `allowBuilds`。第一阶段只开放纯 JS 依赖（react/phaser/pixi.js/matter-js/howler/gsap/three），避免 native addon/node-gyp/任意二进制下载/复杂 postinstall，显著降低构建链复杂度与供应链风险。

---

## 12. 三层产物结构（Source / Build Snapshot / Runtime）

```text
games/<game_id>/versions/<version>/
│
├── source/                    ← LLM 负责（业务源码）
│   ├── src/main.ts
│   ├── src/Game.ts
│   └── ...
│
├── build/                     ← 平台决定（构建基础设施 snapshot）
│   ├── package.json
│   ├── pnpm-lock.yaml         ← 必须保存，重建的唯一依赖事实来源
│   ├── pnpm-workspace.yaml    ← 含 allowBuilds
│   ├── vite.config.ts         ← 含 base: './'（硬约束③）
│   ├── tsconfig.json
│   └── build-profile.json     ← builder_version / dependency_catalog_version / template_version
│
└── dist/                      ← Builder 产生（运行时产物）
    ├── index.html
    └── assets/
        ├── index-xxx.js
        ├── index-xxx.css
        └── ...
```

三层各司其职、边界清晰，便于后续 Repair、重建、版本升级、Debug：

* **Source Artifact**：复用现有多文件 Artifact Store 能力（`hosting/store.write_artifact(files)` 已支持多文件 dict），存到独立 `source/` 命名空间，**不进入 Runtime Hosting 的公开资源路径**。不压缩、不打包 tar、不做 CAS。
* **Build Snapshot**：`package.json`/lockfile/vite.config/tsconfig/workspace/build-profile 全部保存。几十到几百个游戏多存几 KB 无需优化。`pnpm-lock.yaml` 必须保存，否则"重新构建"仍需重新解析依赖，不是同一 snapshot。
* **Runtime Artifact**：仅 `dist/`。

**明确永远不保存**：`node_modules/`、`.pnpm-store/`、npm cache、临时 workspace。

---

## 13. Sandbox 执行层（`sandbox/base.py` / `docker.py` / `local.py`）

### 13.1 execute API

```python
execute(
    source,
    build_cmd=None,
    collect_root=".",        # single-html="."，vite="dist"
    network_mode="none",    # Dependency Prepare 阶段才放开
)
```

### 13.2 single-html

```python
execute(source={"index.html": html}, collect_root=".")
# 验收 /workspace/index.html
```

### 13.3 vite

准备完整 workspace（平台 manifest + LLM source），执行 `pnpm install --offline --frozen-lockfile --frozen-store && pnpm build`，采集 `/workspace/dist/`（`collect_root="dist"`），验收 `dist/index.html` 存在。

---

## 14. DependencyPreparer 抽象（同步实现、可异步化设计）

第一阶段**同步执行**（规模小，不引入 Queue/Worker/Job State），但代码结构上独立、幂等：

```python
code_node()
    ↓ sync
DependencyPreparer.prepare(manifest, profile)
    ↓ sync
sandbox.build(...)
```

**不要**在 `code_node` 里直接堆 `subprocess("pnpm...")`；从第一版就抽象成 `DependencyPreparer.prepare(...)`，调用契约稳定，未来异步化时只需：

```text
现在：code_node → sync → DependencyPreparer
未来：code_node → enqueue → DependencyPrepareWorker
```

`prepare()` **从第一版就设计成幂等**，cache key 基于：`builder/toolchain version + dependency catalog version + package manifest + target platform`。这与项目既有幂等约定（`Idempotency-Key + 创建锁 + 执行锁`）一致，未来 worker 化时直接套用。

---

## 15. 编排层 graph.py

`code_node` 调整为：

```text
Code Agent（输出结构化 JSON）
    ↓
parse format
    ├── single-html → old pipeline
    └── project
           ↓ validate dependencies（catalog 校验）
           ↓ generate manifest（平台侧）
           ↓ DependencyPreparer.prepare（联网、幂等）
           ↓ offline sandbox build（断网）
```

构建失败采集 `stdout/stderr/exit code` 返回 Repair Agent。Repair Agent 输入 = 当前源码 + 构建错误 + 允许依赖列表，**只能修改 source files / dependencies**，不能改构建命令/Node 版本/registry/sandbox 设置。

---

## 16. 构建失败与降级

* **Retry**：Vite 工程构建失败 → Repair Agent（带 stderr）→ Build，最多 `build_max_retries` 次。
* **Dependency Error**：如 `Cannot find module "xxx"`，Repair Agent 只能：改为 catalog 允许的 package / 删除错误 dependency / 修改 import / 使用已有依赖；**不能请求任意未知 npm package**。
* **最终降级**：`build_max_retries` 耗尽 → **用当前 design_doc 重新要求 Code Agent 生成 single-html 版本**（不是把多文件工程强行转单 HTML），保证至少有可交付结果。

---

## 17. Playtest

* **single-html**：保持现有逻辑，但逐步提升 Playwright 比例（静态扫描无法验证 JS runtime error / Canvas 创建 / Phaser Scene 启动 / module import 加载）。
* **project/vite**：不跑 `vite preview`，直接对 `dist/` 启动临时静态 HTTP Server（`http://127.0.0.1:<port>/`），Playwright 访问 `/`，验证页面加载、无关键 console error、无 uncaught exception、Canvas/root 节点存在、游戏启动。Node 不属于 Playtest Runtime。

---

## 18. CDN / 外链策略

Vite 构建后的 JS 仍可能含 `fetch`/`WebSocket`/外部字体/图片/第三方 API。CDN Policy 不应只扫 `<script src>`/`<link href>`，还要对 `dist/**/*.html`、`dist/**/*.js`、`dist/**/*.css` 全量 URL 扫描。默认原则：**生成游戏尽量自包含，不依赖任意第三方运行时 API**；允许的外链必须进白名单。

---

## 19. Draft Preview 鉴权（Artifact Path Preview Token）

### 19.1 不采用单文件 presigned URL（见 §2.7）

### 19.2 Preview Token Path

后端提供：

```text
GET /preview/{token}/{game_id}/{version}/
GET /preview/{token}/{game_id}/{version}/assets/*
```

Token 绑定 `game_id + version + owner + expire_at`。后端先验证创建者身份，签发短期 preview token。浏览器加载 `/preview/<token>/<game>/<version>/`，HTML 内相对资源 `assets/index.js` 自动变成 `/preview/<token>/<game>/<version>/assets/index.js`（配合硬约束③ `base: './'`），整树共享同一授权上下文。

### 19.3 发布状态

* Published：`/public/<game_id>/<version>/`，无需 token。
* Draft：`/preview/<token>/<game_id>/<version>/`，短期 token。

---

## 20. CSP

多文件构建后 `script-src 'self'` / `style-src 'self'` / `img-src 'self' data: blob:` / `media-src 'self' blob:`，比依赖 CDN 更易控。按游戏能力逐步开放 `connect-src`/`font-src`/`worker-src`，**默认 `connect-src 'none'`** 除非游戏明确需要网络能力。

---

## 21. 配置项（`config.py`）

```python
build_pipeline_enabled: bool = False       # 灰度开关，关时全部走 single-html
builder_image: str = "gameforge-builder:v1"
pnpm_store_path: str = "/var/cache/gameforge/pnpm-store"
npm_registry: str = "https://registry.npmmirror.com"
build_max_retries: int = 3
artifact_max_size_mb: int = 50             # 含 dist/（可能需上调）
source_artifact_max_size_mb: int = 20
draft_url_ttl_s: int = 600                 # preview token 有效期
```

不再需要 `sandbox_network` / `sandbox_egress_proxy`（Build Sandbox 恒为 `NetworkMode=none`，npm 网络权限仅属于 Dependency Prepare 阶段）。

---

## 22. 平台生成的 package.json（示例）

```json
{
  "private": true,
  "scripts": { "build": "vite build" },
  "dependencies": {
    "phaser": "<catalog 固定版本>",
    "matter-js": "<catalog 固定版本>"
  },
  "devDependencies": {
    "typescript": "<固定版本>",
    "vite": "<固定版本>"
  }
}
```

React 项目额外 `react`/`react-dom` + devDep `@vitejs/plugin-react`。版本全部由平台维护，LLM 不得使用 `latest`/`*`/`^`。

---

## 23. 灰度与兼容

* **Feature Flag** `build_pipeline_enabled=False` 默认关，关时所有游戏走 single-html（零风险回滚）；开后按 routing 分流 `build=none → single-html` / `build=vite → project pipeline`。
* **历史游戏**：legacy 单 HTML artifact 与新 dist artifact 在 Hosting 层并存兼容。

---

## 24. LocalSandbox（本地开发）

优先 Docker Builder；无 Docker 时若本机有 Node/pnpm 则跑本地 build，否则自动退化为 single-html。LocalSandbox 仅用于开发联调，不需复制生产隔离模型。

---

## 25. 风险与对策

| 风险 | 等级 | 对策 |
|---|---|---|
| LLM 多文件工程首次构建成功率较低 | 高 | 结构化输出 + stderr Repair + Retry + single-html fallback |
| LLM 引用不存在 npm 包 | 中 | dependency catalog 校验 |
| npm 供应链风险 | 中 | package allowlist + 固定版本 + pnpm 11 allowBuilds 限制 install scripts |
| 构建代码尝试联网 | 低 | Build Sandbox `NetworkMode=none` |
| shared pnpm store 被污染 | 中 | Dependency Prepare 独占写、Build Sandbox 只读（`--frozen-store`） |
| Builder 升级致旧游戏无法复现 | 中 | 三个版本独立 + lockfile 为重建事实来源 |
| TS 类型错误 | 中 | stderr 回传 Repair Agent |
| dist 过大 | 中 | 仅限 `dist/`，构建产物体积检查 |
| draft 多资源鉴权失败 | 中 | artifact path token（非单文件 presigned URL） |
| preview token 因绝对路径 URL 丢失 | 中 | 硬约束③ `base: './'` + 提示词禁绝对路径/history 路由 |
| shared pnpm store 无限增长 | 低 | 当前规模小，定期 prune |
| Windows 开发环境差异 | 低 | Docker 优先，本地 Node 作 fallback |

---

## 26. 验证点

1. **Builder**：`node -v && pnpm -v` 成功（pnpm 11）。
2. **Dependency Prepare**：首次 `pnpm install --lockfile-only && pnpm fetch` 从 registry 取依赖；再次执行命中 shared store。
3. **Build Sandbox 网络隔离**：容器内 `curl https://example.com` 失败，同时 `pnpm install --offline --frozen-lockfile --frozen-store` 成功。
4. **固定模板构建**：Vite + TS 产出 `dist/index.html`。
5. **allowBuilds**：固定 Vite+TS 模板构建通过，确认 `BUILDER_ALLOWED_BUILDS` 据实形成（esbuild 等）。
6. **React**：固定 React Demo `pnpm build` 成功且浏览器加载成功。
7. **Phaser + Matter**：弹球游戏（renderer=phaser3, dependency=matter-js）走完 generate→fetch→offline build→playtest→hosting 全链路。
8. **base 验证**：dist 产物资源路径为相对 `./assets/...`；preview token 下子资源 200、token 过期/不匹配 403。
9. **Build Repair**：故意 `import foo from "not-exist"`，确认 build failed → stderr → Repair Agent → build success。
10. **Fallback**：持续制造不可修复错误，确认 retries 耗尽 → regenerate single-html → 交付成功。
11. **Artifact**：对象存储有 source/build/dist，无 node_modules/pnpm store/workspace。
12. **Preview 权限**：draft token 有效→index.html/assets 均 200；token 过期→403；token game_id 不匹配→403；非 owner 拿不到 token；published artifact 无 token 正常访问。

---

## 27. 实施阶段

### P1：固定 Builder + 多文件构建（LLM 不参与）

Builder 镜像（Node + pnpm 11 + Vite）；shared pnpm store；固定 Vite+TS Demo；Dependency Prepare（`--lockfile-only`→`fetch`）；offline Build Sandbox（`--offline --frozen-lockfile --frozen-store`）；`collect_root=dist`；`allowBuilds` 据实形成。

**目标**：先证明整条构建基础设施成立。验收：固定工程 → fetch → offline install → vite build → dist/index.html。

### P2：LLM 多文件工程

routing schema；结构化 JSON；dependencies + catalog；基础依赖自动补齐；package.json/workspace/vite.config/tsconfig 平台生成；graph 分流；Source Artifact 存储。

**目标**：LLM 生成的工程能成功构建。

### P3：Playtest + Hosting

dist 静态服务器 + Playwright；多文件 Artifact Hosting；preview token path；CSP。

**目标**：生成、构建、试玩、预览形成闭环。

### P4：Repair + Fallback + Gray Release

build stderr Repair；`build_max_retries`；single-html fallback；feature flag；E2E 测试。

**目标**：达到可灰度上线状态。

---

## 28. 最终存储模型（结论）

构建过程中可能 `source=100KB / node_modules=100MB / pnpm store=数百MB / dist=3MB`，但这些不是同一种数据。**对象存储仅保存 Source Artifact + Build Snapshot + Runtime Artifact（`source/ + build/ + dist/`）**，不保存 node_modules。Build Server 维护 `/var/cache/gameforge/pnpm-store` 供所有游戏构建复用——即便 100 个 React 游戏也不是 100×node_modules 长期存储，长期存储仍只是 100×source + 100×dist。当前规模完全足够。

---

## 29. 最终架构总结

```text
Plan → Code Agent(source only)
  → Manifest Builder(package.json / lockfile / vite config)
  → Dependency Prep(npm network ✅ / game code ❌) → Shared pnpm Store
  → Build Sandbox(network ❌ / offline install / vite build) → dist/
  → Playtest + Artifact Store → Preview / CDN
```

核心原则：

> 共享 pnpm Store，不共享 node_modules。
> node_modules 只存在于临时构建 workspace。
> 对象存储永远不保存 node_modules。
> LLM 生成业务代码，平台控制构建工具和依赖版本。
> 依赖下载阶段可以联网，真正执行 LLM 代码的 Build Sandbox 不联网。
> 最终 Runtime 永远只是静态 dist，不依赖 Node。

---

## 30. 决策记录

* **2026-08-14**：保留 single-html / project 混合形态。
* **2026-08-14**：放弃共享统一 node_modules，改共享 pnpm Store。
* **2026-08-14**：node_modules 为临时构建数据，不进对象存储。
* **2026-08-14**：LLM 不控制 package.json/npm 版本，依赖由平台 catalog 管理。
* **2026-08-14**：放弃 Build Sandbox 经 egress proxy 联网，改 Dependency Prepare 有限联网 + Build Sandbox 完全离线。
* **2026-08-14**：固定 Builder Toolchain 并版本化，不用全局 vite@latest。
* **2026-08-14**：Build 阶段安装完整构建依赖（含 devDependencies），不用 `--prod`；构建完成仅采集 dist/。
* **2026-08-14**：Draft 预览改 Artifact Path Preview Token，不采用单文件 presigned URL。
* **2026-08-14**：当前规模几十到几百游戏，不建 Build Farm / Artifact CAS / 跨游戏去重。
* **2026-08-14（定稿）**：第一阶段删除 capability，只做 dependency catalog；基础依赖由 renderer/ui 自动补齐，Agent 只选额外依赖。
* **2026-08-14（定稿）**：产物结构改为三层 source/ + build/ + dist/，Build Snapshot 必须保存（含 lockfile）。
* **2026-08-14（定稿）**：Dependency Prepare 第一阶段同步执行，代码抽象独立且幂等，未来再 worker 化。
* **2026-08-14（定稿）**：硬约束 ① lockfile 在线生成归属 Dependency Prepare（`--lockfile-only`→`fetch`）。
* **2026-08-14（定稿）**：硬约束 ② Build Sandbox `NetworkMode=none` + `--offline --frozen-lockfile --frozen-store`。
* **2026-08-14（定稿）**：硬约束 ③ Vite `base: './'` 平台级不可覆盖，连带禁绝对路径 URL 与 history 路由。
* **2026-08-14（定稿）**：硬约束 ④ lifecycle scripts 用 pnpm 11 `allowBuilds`（pnpm-workspace.yaml），不用 `--ignore-scripts`。
* **2026-08-14（定稿）**：三个版本（builder / dependency_catalog / template）各自独立演进，不绑死；lockfile 为重建事实来源。
