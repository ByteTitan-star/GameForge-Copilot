# ADR-07: Production Security Baseline

> **【安全阅读 · 第 8 步选读 · 约 30–45min · 与「内容护栏」正交】**
> 内容审核看 `forge/guard.py`（A 线）；本文是上线前基线（B 线）：密钥 / manifest / 认证 / SSRF / Dev 路由 / 配额试用。
> 代码落点：`llm/url_safety.py`、`forge/build/manifest.py`、`config.dev_routes_enabled`。
> 完整顺序见 `backend/app/forge/guard.py` 文件头。

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P0-1, P0-2, P1-17～23；[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)
* Source review: [2026-08-16-full-project-design-review.md](../2026-08-16-full-project-design-review.md)

---

## Context

全项目设计审查确认：生产可因默认 `jwt_secret`、LLM 产物覆盖 manifest、验证码/OAuth/SSRF/dev 路由/试用账号等路径被接管或横向移动。这些不是「以后优化」，而是上线前安全基线。

**核实：** P0-1/2、P1-17～20 已在源码属实；P1-21～23 机制属实。

## Decision

### 1. 密钥与启动门禁（P0-1）

1. `env != development` 时：若 `jwt_secret` 等于默认值或长度 &lt; 32，**拒绝启动**。
2. 开发环境允许默认值；生产/预发必须来自环境变量或密钥管理，禁止写入仓库。
3. 由 `jwt_secret` 派生的 Fernet 密钥（LLM apikey 加解密）继承同一门禁——无独立「弱默认」。

### 2. LLM 工作区合并与 packageManager（P0-2）

1. `merge_workspace` 对 `source_files` 施加 **保留文件黑名单**（至少：`package.json`、`pnpm-workspace.yaml`、`vite.config.*` 及平台生成的锁文件/约束文件），禁止覆盖平台 manifest。
2. `packageManager` 仅允许匹配 `^pnpm@\d+(\.\d+)*$` 的值再拼接；否则忽略并回落固定版本。
3. `builder_backend=local` 视为高风险开发路径：文档与默认配置明确「禁止在共享/多租户宿主上启用」。

### 3. 认证与账号（P1-17 / P1-18）

1. `/auth/verify-email` 必须与 register/login 同级限流（IP + 邮箱双键）；校验失败达到阈值后作废验证码并要求重发。
2. OAuth callback：仅当已存在用户的 `email_verified=True` 时才按 email 绑定；否则走「验证后合并」或拒绝静默绑定，并避免把受害者困在未验证账号。

### 4. SSRF（P1-19）

1. 用户可控的 `openai_compat` `base_url`：协议白名单（仅 https，开发可放宽 http+localhost）+ 主机黑名单（环回、链路本地、私网、云 metadata）。
2. `test_draft_config` 与 `create_config` 共用同一校验；校验失败返回 400，不发请求。

### 5. Dev 路由（P1-20）

1. Dev 调试路由 **不得** 仅依赖 `env == "development"` 字符串；增加显式开关（默认 **关**），例如 `DEV_ROUTES_ENABLED=false`。
2. 仅当显式开启且（可选）绑定本机监听时才挂载；生产配置检查清单必须包含该项。

### 6. 构建供应链（P1-21）

1. 共享 pnpm store 不得被不可信 prepare 阶段任意 rw 污染跨租户产物：优先 **按租户/按 run 隔离 store**，或 prepare 出站走代理白名单 + store 写入完整性校验。
2. 与 Decision §2 一并视为上线前项；不能只修黑名单不修 store。

### 7. 配额与试用（P1-22 / P1-23）

1. Token 配额：除 `start_run` 外，在 `call_llm` 记账路径检查余量；超限将 run 转为可恢复暂停（或等价 QPAUSED），禁止「启动时剩 1 token、中途无限烧」。
2. Trial 用户：烧钱与建状态 API（创建游戏、LLM config、start run、publish 等）统一依赖注入拦截；或给 trial 独立极小配额。公开试用口令不得视为安全边界。

## Consequences

* 漏配密钥时服务起不来（优于静默被接管）。
* LLM 无法再通过覆盖 `package.json` 绕过 allowBuilds；local builder 命令注入面关闭。
* 验证码爆破、OAuth 预注册劫持、SSRF、dev 信息泄露、试用账号滥用的攻击面显著缩小。
* 配额与 trial 从「前端承诺」变为后端强制，可能改变现有试用体验——产品文案需同步。

## Non-goals

* 完整 WAF / 零信任网络改造。
* 将 refresh token 迁 httpOnly cookie（见 ADR-12，可延后）。
