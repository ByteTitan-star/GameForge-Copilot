# ADR-03: Sandbox Provider Strategy

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: [sandbox-data-flow.md](./sandbox-data-flow.md), [../sandbox-e2b-benchmark.md](../sandbox-e2b-benchmark.md), [ADR-11](./ADR-11-sandbox-hosting-resources.md), [ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

## Context

Choose sandbox provider for isolated game build/execute: Docker vs E2B (or hybrid).

## Decision

1. **Preferred backend: E2B** (`sandbox_backend=e2b`, `sandbox_e2b_enabled=true`).
2. **Secret**: `E2B_API_KEY` must come from environment / secret store — never committed.
3. **Fallback**: if E2B is selected but key missing / disabled, factory falls back to
   `docker`, then `local` so developer machines and CI do not hard-fail.
4. **Tier auto**: `sandbox_tier_auto=true` picks `lite|standard|heavy` from engine/size/telemetry;
   base tier remains `sandbox_default_tier=standard`.
5. Network: `e2b_allow_internet=false` by default.

## Consequences

* Production-like runs should set a real `E2B_API_KEY`.
* Benchmark table in `sandbox-e2b-benchmark.md` remains the ops scorecard for cost/latency.
* Data egress via E2B is accepted by Owner for this project configuration.

---

## Revision 2026-08-16（设计审查后）

* Status: **Accepted**
* Accepted-by: ByteTitan-star
* Date: 2026-08-16

### 新增决策

1. **部署现实优先于「默认常量」：**  
   `docker-compose.yml` 当前将 `SANDBOX_BACKEND` / 构建链设为 **docker**。在 E2B 密钥、会话对账与 ADR-11 启用前置未满足前，**Docker（及必要时 local）路径的安全与资源加固是生产必做项**，不得以「ADR 写了首选 E2B」跳过。
2. **回退路径同等约束：**  
   Fallback 到 docker/local 时，仍须遵守 ADR-07（manifest / packageManager）、ADR-11（failure_kind、AutoRemove、日志轮转、uid 对齐、路径校验）。`local` + Windows builder 禁止用于多租户宿主。
3. **Tier 配置单表：**  
   `lite|standard|heavy` 的 CPU/内存/超时映射收敛到单一配置源；禁止 `docker.py` / `local.py` / builder settings 三套魔法数长期并存。  
   澄清审查误表述：heavy **并非死代码**——`recommend_tier` 可在引擎/体量/压力信号下返回 heavy；待修的是配置分裂与透传一致性。
4. **E2B 启用门槛：**  
   启用前须完成 ADR-11 §7（会话句柄持久化 + 定时对账）。未完成前保持 Docker 为 compose 默认部署后端是可接受的显式选择，但应在运维文档写明，避免与 `config.py` 默认值互相「以为对方是真相」。

### 修订后后果

* 文档、compose、config 三者允许短期不一致，但 **必须在 FLAG-INVENTORY / 运维手册标明「当前部署后端」**。
* ADR-11 成为 Docker/local 加固的配套决策；本 ADR 只定选型与门槛，不重复列出全部 HostConfig 细则。
