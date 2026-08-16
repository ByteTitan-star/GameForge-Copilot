# ADR-09: Timeout & IO Boundaries

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P0-4, P1-10, P1-11, P2-25；[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

---

## Context

审查将「worker 死锁」澄清为：**无超时 IO 永久占用并发槽位的活锁**。Postgres / Redis / Docker 客户端缺少底层超时；图节点 TimeoutPolicy 未覆盖 `done` 与部分 finally 清理；审核调用未尊重 `audit_request_timeout`；`code_or_repair` 节点预算与内部串行工作量系统性错配；LangGraph `RetryPolicy` 未排除业务性异常。

**核实：** `db.py` / `redis.py` 无超时参数；`done` 节点无 TimeoutPolicy；`RetryPolicy` 未传 `retry_on`——属实。

## Decision

### 1. 基础设施客户端统一超时（P0-4）

1. asyncpg / SQLAlchemy：配置连接与 `command_timeout`（或等价），禁止无限等待行锁/假死连接。
2. Redis：配置 `socket_connect_timeout` / `socket_timeout`（或 asyncio 客户端等价项）。
3. aiodocker / 镜像拉取 / `container.delete`：一律 `asyncio.wait_for`（或封装层），清理路径不得在超时策略之外无限 await。
4. 超时值进 `config.py` 单表，禁止各模块魔法数。

### 2. 图节点 TimeoutPolicy（P0-4）

1. `done` 与所有有外部 IO 的节点一律挂 TimeoutPolicy。
2. 节点被取消后的 finally 清理必须走带超时包装的同一工具函数。

### 3. 审核超时语义（P1-10）

1. 所有 `guard.audit`（流式前同步、后台 task）统一 `asyncio.wait_for(settings.audit_request_timeout)`。
2. `audit_request_timeout` 表示端到端审核预算，不得仅覆盖「流末等窗」而让 `complete()` 吃满 LLM 读超时 × 重试。

### 4. code_or_repair 预算（P1-11）

1. 当 `build_pipeline_enabled=True` 时，节点 TimeoutPolicy 预算按 build 链动态计算（类比 `code_qa_loop` 外墙的 `attempts × per`），使 `build_max_retries` 有意义。
2. 预算与配置项可观测（metrics/日志），避免静默错配。

### 5. RetryPolicy 可重试集合（P2-25）

1. `RetryPolicy` 必须传 `retry_on`：排除 `ContentAttacked`、`RunFinalized`、明确的 `AppError` 业务失败等「再试也无意义 / 有害」的类型。
2. 瞬时 IO / 超时类才进入节点级重试；与 httpx、code_qa attempt、build 环、worker 重投的乘法效应要有文档化上限意识。

## Consequences

* 挂起 IO 不再永久占满 `max_concurrent_tasks`；故障可失败可告警。
* 动态预算可能拉长单节点墙钟时间——需与 ADR-08 的 `consumer_timeout` / 租约策略一起调。
* 攻击流量与配置错误不再被 RetryPolicy 成倍放大。

## Non-goals

* 分布式追踪全链路采样策略（可另开观测 ADR）。
* 修改 LLM 供应商 SLA。
