# ADR-11: Sandbox & Hosting Resources / SoT

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P1-12～16, P2-1/3/6/21～23；衔接 [ADR-03](./ADR-03-sandbox-provider-strategy.md)；[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

---

## Context

Sandbox / builder / hosting 在故障分类、容器生命周期、日志、进程组、路径校验与 Hosting SoT 上不一致。Compose 部署强制 Docker（见 ADR-03 修订），因此 Docker 路径加固是生产问题，不是「仅 local 开发」。

**核实：** DockerError 吞成 build 文案、无 AutoRemove/LogConfig、WS relay 泄漏、local 无进程组、`write_version_layers` 穿透 local——属实。P2-6「heavy 不可达」为 **部分属实**（auto 可选 heavy；问题是配置三处分裂）。

## Decision

### 1. failure_kind 贯通（P1-12 / P2-3）

1. `BuildResult`（及同类）携带结构化 `failure_kind`：至少 `infra` / `build` / `timeout` / `oom`。
2. Docker daemon / 拉镜像失败标 `infra`，**不得**进入 LLM 修复烧 token 循环。
3. Reliability 分类只消费类型字段，禁止依赖中文错误字符串嗅探；`sandbox_failed` HITL 必须有真实写入点。

### 2. 容器与临时目录生命周期（P1-13 / P1-14）

1. 容器 HostConfig：`AutoRemove`（或等价）+ 日志轮转（如 json-file `max-size`/`max-file`）。
2. `container.log` 使用 `tail=N`，禁止无界读入 worker 内存。
3. Worker 启动时清扫命名前缀孤儿容器与 `gf-*-sandbox-*` 类临时目录。

### 3. 进程组与路径纵深（P1-16 / P2-23）

1. Local / shell builder：POSIX `start_new_session` + 杀进程组；Windows 用 Job Object 或文档化等价方案。
2. Backend 写文件时校验 `rel` 规范化后仍在 workspace 内，不唯依赖调用方 `_normalize_files`。

### 4. Docker 用户与 tier 配置（P2-21 / P2-6）

1. `DockerSandbox` 复用 builder 的 uid/user spec 与 bind mount 权限对齐，避免 EACCES / 不必要的 root。
2. `tier → 资源/超时` 收敛进 `config.py`（或单一模块表）；`docker` / `local` / `builder` 禁止各写一套魔法数。
3. `get_sandbox().create` 支持 tier 透传；auto 推荐与显式 tier 行为可测。

### 5. HostingBackend 协议补全（P2-1）

1. `write_version_layers`、删除/prune、目录语义纳入 `HostingBackend`；禁止 store 门面永远写 local 而声称 OSS 为 SoT。
2. 若保留本地 cache：文档明确 cache vs SoT，prune 必须同时清理远端对象。

### 6. WS relay 生命周期（P1-15）

1. Relay task 创建后立即纳入 try/finally；`ready.wait` / replay / disconnect 全覆盖。
2. 客户端在 replay 期断开必须取消 relay，禁止 exclusive 队列与 memory bus 无界堆积。

### 7. Daytona 启用前置（P2-22）

1. 远端 sandbox id 须可跨进程对账回收：除进程内热缓存外，须登记到共享存储（如 Redis），
   worker 启动时对「已登记但不在本进程热缓存」的句柄执行 delete；禁止仅依赖模块级 `_LIVE`。
2. `destroy` 在热缓存未命中时仍须按 `session.handle` 走 API 删除，避免泄漏计费。
3. 未满足对账前，compose 保持可观测的 Docker 路径是可接受的显式选择（与 ADR-03 修订一致）。

## Consequences

* Infra 故障不再伪装成「代码质量差」；磁盘/内存打满风险下降。
* Hosting 多后端行为一致，OSS 泄漏可治理。
* tier 单表可能改变个别引擎的超时体感——需回归构建超时用例。

## Non-goals

* 立刻切断 Docker/local 回退路径（仍由 ADR-03 + 密钥/对账就绪决定）。
* 重写整个构建流水线产品形态。
