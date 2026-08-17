# ADR-03: Sandbox Provider Strategy

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: [sandbox-data-flow.md](./sandbox-data-flow.md), [../sandbox-daytona-benchmark.md](../sandbox-daytona-benchmark.md), [ADR-11](./ADR-11-sandbox-hosting-resources.md), [ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

## Context

Choose sandbox provider for isolated game build/execute: Docker vs Daytona (or hybrid).

## Decision

1. **Preferred backend: Daytona** (`sandbox_backend=daytona`, `sandbox_daytona_enabled=true`).
2. **Secret**: `DAYTONA_API_KEY` must come from environment / secret store — never committed.
3. **Fallback**: if Daytona is selected but key missing / disabled, factory falls back to
   `docker`, then `local` so developer machines and CI do not hard-fail.
4. **Tier auto**: `sandbox_tier_auto=true` picks `lite|standard|heavy` from engine/size/telemetry;
   base tier remains `sandbox_default_tier=standard`.
5. **Abandoned**: E2B is fully removed from this codebase; do not reintroduce.

## Consequences

* Production-like runs should set a real `DAYTONA_API_KEY` (`uv sync --extra daytona`).
* Benchmark table in `sandbox-daytona-benchmark.md` remains the ops scorecard for cost/latency.
* Data egress via Daytona is accepted by Owner for this project configuration.

---

## Revision 2026-08-17（E2B → Daytona）

* Status: **Accepted**
* Accepted-by: ByteTitan-star
* Date: 2026-08-17

### 新增决策

1. **云沙箱供应商切换为 Daytona**：删除全部 E2B 适配与依赖；配置项改为 `DAYTONA_*` / `sandbox_daytona_enabled`。
2. **部署现实优先于「默认常量」：**
   `docker-compose.yml` 可将 `SANDBOX_BACKEND` 设为 **docker**。在 Daytona 密钥、会话对账与 ADR-11 启用前置未满足前，**Docker（及必要时 local）路径的安全与资源加固是生产必做项**。
3. **回退路径同等约束：**
   Fallback 到 docker/local 时，仍须遵守 ADR-07（manifest / packageManager）、ADR-11（failure_kind、AutoRemove、日志轮转、uid 对齐、路径校验）。`local` + Windows builder 禁止用于多租户宿主。
4. **Daytona 启用门槛：**
   启用前须完成 ADR-11 §7（会话句柄持久化 + 定时对账）。未完成前保持 Docker 为 compose 默认部署后端是可接受的显式选择。

### 修订后后果

* 文档、compose、config 三者允许短期不一致，但 **必须在 FLAG-INVENTORY / 运维手册标明「当前部署后端」**。
* ADR-11 成为 Docker/local 加固的配套决策；本 ADR 只定选型与门槛，不重复列出全部 HostConfig 细则。
