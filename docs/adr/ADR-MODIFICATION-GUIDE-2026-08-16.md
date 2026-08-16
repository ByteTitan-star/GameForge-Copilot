# ADR 修改指南（2026-08-16 全项目设计审查）

* Status: **Guide**（配套决策均已 Accepted；见 ACCEPT-CHECKLIST）
* Source: [2026-08-16-full-project-design-review.md](../2026-08-16-full-project-design-review.md)
* Date: 2026-08-16
* Accepted-by: ByteTitan-star

---

## 1. TL;DR

1. 审查报告中的 **P0 / 多数 P1 在源码中属实**，应转化为可签字的 Architecture Decision，而不是直接当实现工单堆砌。
2. 按 **决策边界** 拆成 **6 份新 ADR（07～12）**，并 **修订 ADR-03、ADR-05**；现有 ADR-01/02/04/06 本次不改正文。
3. 本指南给出：**核实结论 → 映射表 → Accept 顺序 → 各 ADR 链接**。实现计划另开；此处不改业务代码。

---

## 2. 核实方法与口径

| 口径 | 含义 |
| --- | --- |
| **属实** | 源码/compose 可定位到审查描述的机制；后果链路成立 |
| **部分属实** | 机制存在，但严重度、触发条件或「完全不可达」等表述需收窄 |
| **夸大 / 误报** | 关键断言与当前代码不符（本次极少） |
| **未逐行复验** | 机制同类、或依赖组合路径；接受审查结论但实施前再 spot-check |

抽查覆盖：`config.py`、`manifest.py`、`builder.py`、`docker-compose.yml`、`db.py`、`redis.py`、`worker.py`、`graph.py`、`auth.py`、`oauth.py`、`trial.py`、`ws/runs.py`、`ForgePage.tsx`、`ws/client.ts`、`hosting/store.py`、`reliability/policy.py`、`sandbox/tiers.py` 等。

---

## 3. 核实结论摘要

### 3.1 P0 — 全部属实

| ID | 结论 | 证据要点 |
| --- | --- | --- |
| P0-1 | **属实** | `jwt_secret` 有可用默认值；无 `env != development` fail-fast |
| P0-2 | **属实**（RCE 面收窄） | `merge_workspace` 无保留文件黑名单；`packageManager` 仅 `startswith("pnpm@")` 后拼进 `create_subprocess_shell`。**宿主机 RCE** 主要在 `builder_backend=local` + Windows；Docker builder 仍有 manifest 覆盖与供应链面 |
| P0-3 | **属实** | `docker-compose.yml` 的 `backend`/`worker` **无** `restart:` |
| P0-4 | **属实** | `create_async_engine` 无 statement/command timeout；Redis pool 无 socket timeout；`done` 节点未挂 `TimeoutPolicy`（其它节点有） |

### 3.2 P1 — 核心项属实（节选）

| ID | 结论 | 备注 |
| --- | --- | --- |
| P1-1～4 | **属实** | 整 run 包在 `message.process`；busy 路径 `sleep(2)` 且不递增 retry；崩溃重投 `resume=False` |
| P1-5 | **属实** | `try_begin_side_effect` → `promote` → `commit` 顺序 |
| P1-6 | **属实** | `user_pause` 检查点仅 `design_doc`；恢复路由强制 `art_options` |
| P1-7 | **属实** | `resume_grant` 与 `RUNNING` 同事务消费；scheduler 只回收 PAUSED |
| P1-8/9 | **属实** | 邮件与 run 同队列；失败立即 republish；DLQ 无消费者 |
| P1-10/11 | **属实** | audit 未对齐 `audit_request_timeout`；`code_or_repair` 预算与内部串行工作量错配 |
| P1-12～16 | **属实** | DockerError→build 文案；无 AutoRemove/LogConfig；WS relay 在 try 外；local kill 无进程组 |
| P1-17～20 | **属实** | verify-email 无限流；OAuth 绑定不查 `email_verified`；base_url 无主机限制；dev 路由靠 `env==development` |
| P1-21～23 | **属实** | prepare 联网 + 共享 store rw；配额仅 start_run 检查；trial 拦截面极窄 |
| P1-24～26 | **属实** | 切游戏不重置 state；WS 重连用闭包旧 token；`fetchDraftHtml` 自刷新绕过单飞 |

### 3.3 需收窄的表述

| ID | 审查原文 | 核实后 |
| --- | --- | --- |
| P2-6 | 「heavy 档不可达」 | **部分属实**。`resolve_create_tier` / `recommend_tier` **可以**返回 `heavy`（引擎/体量/近期压力）。真问题是 **docker/local/builder 三处超时与资源表分裂**，以及 create 未传 explicit tier 时依赖 auto 启发式 |
| ADR-03 vs compose | 「生产首选 E2B」 | **配置分裂**。`config` 默认 `sandbox_backend=e2b`，但 **compose 强制 `SANDBOX_BACKEND=docker`**。部署路径上 Docker 加固不可因「ADR 写了 E2B」而跳过 |
| P0-2 RCE | 「Windows 本地 builder RCE」 | **属实但范围收窄**：local+Windows 为命令注入；全后端均受 manifest 覆盖影响 |

### 3.4 P2 — 抽样属实，批量纳入 ADR-12 / 专项 ADR

Hosting 穿透 local（P2-1）、HITL 词表多处复制（P2-2）、中文错误嗅探（P2-3）、checkpoint revision 未消费（P2-4）、RetryPolicy 无 `retry_on`（P2-25）等已 spot-check 或与 P1 同根。其余 P2 按「同类机制」纳入 ADR-12，实施前再逐条复验。

---

## 4. 与现有 ADR 的关系

| 现有 ADR | 本次动作 | 原因 |
| --- | --- | --- |
| ADR-01 降级产物发布 | **不改** | 与审查无冲突；promote 幂等时序由 ADR-10 补 |
| ADR-02 偏好保留 | **不改** | 范围外 |
| ADR-03 沙箱选型 | **修订** | 写明 compose/回退路径仍须 Docker/local 加固；tier 配置收敛 |
| ADR-04 会话存储 | **不改** | 范围外 |
| ADR-05 可恢复暂停 | **修订** | 补充检查点合并语义、phase 词表归属、与 grant/RUNNING 回收的边界 |
| ADR-06 语义缓存 | **不改** | 范围外（与 FLAG 默认值一致性另议，不在本次） |

---

## 5. 新建 / 修订 ADR 一览

| ADR | 文件 | 覆盖审查项 | 建议 Status |
| --- | --- | --- | --- |
| [ADR-07](./ADR-07-production-security-baseline.md) | 生产安全基线 | P0-1/2，P1-17～23 | **Accepted** |
| [ADR-08](./ADR-08-worker-messaging-reliability.md) | Worker / 消息可靠性 | P0-3，P1-1～4/8/9 | **Accepted** |
| [ADR-09](./ADR-09-timeout-and-io-boundaries.md) | 超时与 IO 边界 | P0-4，P1-10/11 | **Accepted** |
| [ADR-10](./ADR-10-checkpoint-hitl-idempotency.md) | Checkpoint / HITL / 幂等 | P1-5/6/7，P2-2/4/7/12 | **Accepted** |
| [ADR-11](./ADR-11-sandbox-hosting-resources.md) | Sandbox / Hosting 资源与 SoT | P1-12～16，P2-1/3/6/21～23 | **Accepted** |
| [ADR-12](./ADR-12-api-frontend-ops-debt.md) | API / 前端 / 运维债 | P1-24～26，其余 P2 | **Accepted** |
| [ADR-03 修订](./ADR-03-sandbox-provider-strategy.md) | 沙箱策略补强 | P2-6/21/22 + compose 现实 | **Accepted** |
| [ADR-05 修订](./ADR-05-recoverable-pause-representation.md) | 暂停表示补强 | P1-6/7，P2-2 | **Accepted** |

---

## 6. 审查项 → ADR 完整映射

### P0

| ID | ADR |
| --- | --- |
| P0-1 | ADR-07 |
| P0-2 | ADR-07（+ ADR-11 store/隔离相关） |
| P0-3 | ADR-08 |
| P0-4 | ADR-09 |

### P1 可靠性

| ID | ADR |
| --- | --- |
| P1-1, P1-2, P1-3, P1-4 | ADR-08 |
| P1-5, P1-6, P1-7 | ADR-10（衔接 ADR-05） |
| P1-8, P1-9 | ADR-08 |
| P1-10, P1-11 | ADR-09 |
| P1-12 | ADR-11（failure_kind） |
| P1-13, P1-14, P1-15, P1-16 | ADR-11 |

### P1 安全

| ID | ADR |
| --- | --- |
| P1-17～23 | ADR-07 |

### P1 前端

| ID | ADR |
| --- | --- |
| P1-24, P1-25, P1-26 | ADR-12 |

### P2

| ID | ADR |
| --- | --- |
| P2-1, P2-3, P2-6, P2-21～23 | ADR-11 / ADR-03 |
| P2-2, P2-4, P2-7, P2-12 | ADR-10 / ADR-05 |
| P2-5, P2-8～11, P2-13～20, P2-24～30 | ADR-12 |
| P2-25 RetryPolicy | ADR-09（与超时/重试同策）或 ADR-12；**决策写入 ADR-09** |

---

## 7. 建议 Accept / 实施顺序

与审查「修复优先级」对齐，但以 **ADR 签字** 为单位：

| 批次 | ADR | 对应审查批次 |
| --- | --- | --- |
| **A（上线前）** | ADR-07、ADR-08、ADR-09；ADR-03/05 修订段 | P0 + 安全五连 + 消息丢失 + 超时 |
| **B（一周内）** | ADR-10、ADR-11 | Worker 状态机 + sandbox/WS 泄漏 |
| **C（排期）** | ADR-12 分节 Accept | 配额、API 债、前端体验、运维 |

**跨 ADR 共享根因（实施时合并 PR 亦可）：**

1. 超时体系 → ADR-09  
2. `failure_kind` 贯通 → ADR-11  
3. Checkpoint 单一真相源 → ADR-10  
4. HITL 域层收口 → ADR-10 + ADR-05  
5. HostingBackend 协议补全 → ADR-11  

---

## 8. Accept 检查建议

签字前至少确认：

- [ ] 每份 ADR 的 Decision 可映射到可测验收（测试或运维检查项）
- [ ] ADR-07 与 CLAUDE.md「禁硬编码密钥」一致  
- [ ] ADR-03 修订后，compose 的 `SANDBOX_BACKEND=docker` 不再与文档矛盾  
- [ ] ADR-05/10 对 `user_pause` / `resume_grant` / RUNNING 回收无互相打架的表述  
- [ ] ADR-12 标明哪些条款可延后，避免「一纸 Accept 绑死全部 P2」

机器证据：可后续扩展 `tests/test_adr_evidence.py`（现有文件仅覆盖 ADR-02/03/04 类不变量）。

---

## 9. 明确不在本次指南范围

- 实现代码与具体 PR 拆分（用 writing-plans / 实现会话）
- ADR-06 / Pinecone / 偏好抽取路径变更
- 敏感词检测文档、官方小游戏资源是否迁出等产品决策（审查 CLAUDE 违反表仅记录，不升格为 ADR-07 强制项，除非 Owner 另批）

---

*本指南随 ADR-07～12 与 ADR-03/05 修订一并维护；审查原文仍以 `docs/2026-08-16-full-project-design-review.md` 为问题清单 SoT。*
