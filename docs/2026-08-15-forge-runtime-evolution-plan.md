# Forge Runtime 演进计划 v2

* Status: In Progress（**P0–P5 MVP 主体已落地**；P3 E2B 生产切换、P4.5 Semantic、Pending ADR 细项仍 gated）
* Date: 2026-08-15
* Owners: TBD
* Reviewers: TBD
* Related:
  * [CodeQaLoop 设计](./superpowers/specs/2026-08-15-code-qa-loop-design.md)（硬约束）
  * `backend/app/forge/graph.py` / `subgraphs/code_qa_loop.py`
  * `backend/app/sandbox/`、`backend/app/forge/skills/`、`backend/app/forge/cache/`
  * `backend/app/forge/memory/`（P1 ContextBuilder / Summary / Preferences；P5 Enforcement）
  * [ADR 归档](./adr/README.md)
* ADR 状态:
  * **ADR-01** Degraded Artifact Publishing — **Accepted**（见 `docs/adr/`）
  * **ADR-05** Recoverable Pause Representation — **Accepted**（见 `docs/adr/`）
  * **ADR-02** Preference Retention — **Proposed**（Explicit 保留；Inferred 不覆盖 Explicit；删 Game 不自动清 Inferred）
  * **ADR-03** Sandbox Provider Strategy — **Proposed**（生产默认 Docker；E2B 仅 PoC）
  * **ADR-04** Conversation Storage Migration — **Proposed**（`forge_messages` 唯一 SoT）
* Implementation decisions（非 ADR）:
  * Context Builder：**P1 MVP 建立规范路径；P5 Enforcement 拆除遗留拼装**
* 落地进度（相对本仓库）:
  * **P0** ✅ 错误分类 / node timeout / `pause_reason` / 幂等副作用 / ADR-01 产物门禁（PR `#65`）
  * **P1** ✅ ContextBuilder / Preferences（PR `#72`）；session summary 刷新（PR `#74`）；可选 LLM summary（PR `#81`）；可选 Inferred 偏好
  * **P2** ✅ Skills catalog/router（PR `#75`）；Art/QA prompt；可选 LLM Methodology 自选（`skills_llm_selection` 默认关）；**离线 eval 套件**（precision@1 / member hit / body reduction lift）
  * **P3** ✅ SandboxBackend；Docker 生产基线；E2B **真 SDK 适配**（`--extra e2b`，默认禁用）；HITL destroy+restore；**tier telemetry 推荐**（`sandbox_tier_auto` 默认关）；data-flow / benchmark 清单
  * **P4** ✅ Redis Exact Cache 白名单 MVP；`skill_bundle_hash`；Semantic shadow 骨架（PR `#78`/`#81`）
  * **P5** ✅ ContextBuilder Enforcement + spans + ADR 归档（PR `#79`/`#80`）；**遗留 concat 双路径已拆除**
  * **仍 gated** 带真实 LLM 的 quality-lift A/B / E2B 生产切换（SDK 已接但默认关）/ ADR Accept 签字 / 全量 Load

---

## 0. 总体原则

本次升级**不以“重写 Runtime”为目标**，而以四个问题为主线：

1. **可靠性**：单节点的可恢复故障不能销毁整个 Run。
2. **上下文能力**：建立 Session Memory 与用户偏好，但避免过早引入复杂向量基础设施。
3. **Agent 能力**：把现有 prompt snippets 升级为标准 Skill，同时明确平台 Policy 永远高于 Agent 自主选择。
4. **执行隔离**：验证 E2B 是否优于现有 Docker，再决定迁移，而不是先假定 E2B 一定替换 Docker。

每个 P 阶段必须具备：

* MVP Scope
* Explicit Out-of-Scope
* Feature Flag
* 旧模块映射
* 退出条件 / Go·No-Go 指标
* Rollback path

**只有上一阶段指标证明有必要，才进入下一阶段。**

目标形态（增量可达，非一次性切换）：

```text
LangGraph Workflow（串行）
        │
        ▼
 entry_router
        │
        ▼
   Plan Agent
        │
        ▼
    Art Agent
        │
        ▼
 Code + QA Loop（现有 CodeQaLoop，核心保留）
        │
        ▼
      Done
```

Plan / Art / Code 是**串行逻辑角色**，不表示并行执行。

横向能力：

```text
┌──────────────────────────────────────────────┐
│ Platform Policies                            │
│ Security / CDN / Engine / Audit / Quota / QA │
└──────────────────────────────────────────────┘

┌────────────┐ ┌────────────┐ ┌───────────────┐
│ Memory     │ │ Skills     │ │ Sandbox       │
│ Context    │ │ Router     │ │ Runtime       │
└────────────┘ └────────────┘ └───────────────┘

┌──────────────────────────────────────────────┐
│ Reliability / Usage / Trace / Cache          │
└──────────────────────────────────────────────┘
```

系统定位：

> Forge 是以 LangGraph 为可靠编排层、以 bounded agent nodes 为智能执行层、以 Agent Skills 为能力扩展层、以独立 Memory 为个性化基础、以可插拔 Sandbox Backend 为隔离执行环境的游戏生成 Agent Runtime。

**不需要变成 Multi-Agent 自治系统。**

核心概念分离：

```text
Memory ≠ Cache ≠ Checkpoint ≠ Conversation History
```

---

## 硬约束：CodeQaLoop

任何 Sandbox、Skill、Memory、Cache、可靠性重构**不得削弱**现有 CodeQaLoop 的：

* 有界 attempt（`code_qa_max_attempts`）
* candidate 管理与 promote 语义
* B 档 Playwright 可交互冒烟硬门禁
* 禁止静态 DOM / 源码检查冒充生产 `qa_ok`
* infra / product / build 失败分流

CodeQaLoop 是已有可靠性资产，不是待替换遗留代码。未来只增强其外围：

```text
CodeQaLoop
├── better Agent / Skills
├── better Sandbox Backend
└── better Recovery / Idempotency
```

禁止：

```text
Playwright 不可用 → deterministic / static QA fallback → qa_ok
```

正确路径：

```text
Playwright / Chromium 不可用
  → failure_kind=infra（或等价）
  → retry / PAUSED_RECOVERABLE / 运维告警
  → 不得标记为 QA 通过
```

---

# P0：先补可靠性，不重写整个状态机

## P0 MVP

第一阶段只做四件事。

### 1. 统一错误分类

最小错误体系：

```text
RecoverableError
├── ProviderTimeout
├── ProviderRateLimit
├── Provider5xx
├── InvalidModelOutput
├── SandboxTimeout
├── SandboxOOM
└── WorkerInterrupted

UserActionRequired

FatalError
├── DataCorruption
├── InvariantViolation
└── SecurityViolation
```

原则：

```text
RecoverableError ≠ Run FAILED
```

仅 FatalError（及明确的用户取消）进入不可恢复终态 `failed`。

**BYOK 说明**：用户自带单一 provider key 时，不默认假设存在平台级 provider fallback。可恢复路径优先：retry →（若用户配置了备用）fallback model → `status=paused` + `pause_reason=recoverable_error` / template 降级（按节点定义）。平台审核模型与用户生成模型分离，互不冒充。

### 2. LangGraph 节点 Timeout

为现有节点配置明确 timeout（利用 `langgraph>=1.2` 的 `TimeoutPolicy` / `RetryPolicy`），统一落在：

```python
NODE_EXECUTION_POLICIES = {
    "entry_router": ...,
    "plan": ...,
    "art": ...,
    "code_qa_loop": ...,  # 或拆分子策略，见下
}
```

禁止 timeout 散落在各节点业务代码里各自 `wait_for`。

**预算对齐（必须）**：

当前默认 `llm_request_timeout=300`。节点 timeout **必须严格大于**该节点内单次 LLM HTTP 读超时，否则正常长生成会被误杀：

```text
HTTP connect < LLM read timeout < Node attempt timeout
```

与 CodeQa / Build 预算正交，禁止相乘误解：

| 预算 | 含义 | 谁拥有 |
| --- | --- | --- |
| `code_qa_max_attempts` | CodeQaLoop 总 attempt（含首次 generate） | 子图 |
| `BUILD_MAX_RETRIES` | 单 attempt 内 Vite 构建修复 | build 内环 |
| Node `max_attempts` | 节点级瞬态故障（网络/5xx）重试 | NodeExecutionPolicy |

**暂定表（标定前）**：以配置为源，表中数值为「下限建议」，实装时取 `max(建议, llm_timeout + margin)`：

| Node | 建议下限 | 备注 |
| --- | ---: | --- |
| entry_router | 10s | 规则路由，无 LLM |
| plan | llm+60s | 含校验重试 |
| art | llm+60s | |
| code_or_repair（单次） | llm+120s | 不含整段 CodeQaLoop 外墙 |
| playtest | 90s | Playwright 墙钟 |
| diagnose | llm+30s | |
| code_qa_loop（外墙） | 按 attempt×(code+playtest+diagnose) 推导 | 或只给子节点 timeout、外墙用 run deadline |

第一版**不**强制完整 Phase/Run deadline hierarchy；有真实误杀/饿死数据后再加。

### 3. 可恢复暂停（ADR-05：不新增 RunStatus）

**P0 不修改 `RunStatus` 枚举。** 对外继续只暴露：

```text
running / paused / done / failed
```

可恢复故障在耗尽 retry/fallback 后进入：

```text
status = paused
pause_reason = recoverable_error
```

示例 payload：

```json
{
  "status": "paused",
  "pause_reason": "recoverable_error",
  "recovery": {
    "node": "code",
    "error_code": "provider_timeout",
    "attempts": 3,
    "can_retry": true
  }
}
```

HITL 等待用户：

```json
{
  "status": "paused",
  "pause_reason": "waiting_user"
}
```

`pause_reason` 初始集合：

```text
paused
├── waiting_user
├── recoverable_error
├── quota_blocked
└── manual_hold
```

流转：

```text
RUNNING
  ├─ success            → next node
  ├─ recoverable error  → retry → fallback → paused (recoverable_error)
  └─ fatal              → FAILED
```

原则：**reason 先行，enum 后置。** 仅当未来多种暂停在查询、SLA、生命周期与 UI 上必须分叉时，再考虑提升为一级 RunStatus。完整状态机重构不在 P0。

须同步约定 `/retry` 与 `hitl/resolve`：对 `recoverable_error` 走重试/恢复，对 `waiting_user` 走 HITL；避免双路径 409。

### 4. 幂等副作用

以下操作必须带 idempotency key：

```text
create version / save candidate
emit final artifact / promote
usage billing
HITL resume 副作用
```

推荐 key：

```text
run_id + node_name + node_execution_id + operation
```

目标：worker 在成功后、ack 前崩溃时，重放不产生重复 version / 重复扣费。

与现有能力对接（复用，不重写）：

* `run:executing:{id}` 执行租约
* create_run Idempotency-Key
* `forge_messages.dedupe_key`

## P0 Out-of-Scope

* 修改 `RunStatus` 枚举 / 新增 `paused_recoverable` status（见 ADR-05）
* 大规模新 Run 状态机（RETRYING/DEGRADED/… 全量枚举）
* Sandbox snapshot orchestration
* 完整独立 Reconciler 平台（可增强现有 lease 心跳，不新造一套）
* 平台级多 provider 动态调度
* 多级 fallback planner
* 分布式 cancellation propagation
* Semantic Cache / Pinecone / E2B 生产切换
* 用静态检测合成 `qa_ok` 或自动 `publishable`（见 ADR-01）

## P0 Feature Flag / Rollback

* Flag 示例：`reliability_node_timeout`、`reliability_pause_reason`、`reliability_idempotent_side_effects`
* Rollback：关 flag → 回退到现有行为；**不引入新 RunStatus**，旧客户端只需继续理解 `paused`

## P0 Go / No-Go

故障注入后：

* 可恢复故障 **0 次**直接 `failed`（无 pause/retry/fallback）
* 可恢复暂停一律为 `status=paused` + `pause_reason=recoverable_error`（无新 enum）
* 同一副作用重放 **不**产生重复 artifact / 重复 usage
* Node timeout 误杀率（正常成功路径被 timeout）低于约定阈值（标定后写入）
* CodeQaLoop 行为回归测试全绿（含「禁止静态 qa_ok」；`previewable` 不得推导 `qa_ok` / `publishable`）

## P0 已关闭的架构歧义

```text
✓ 错误分类
✓ node timeout（对齐 LLM 超时）
✓ recoverable pause = paused + pause_reason（不改 RunStatus）
✓ 幂等副作用
✓ checkpoint 增强现有栈（不迁 checkpointer）
✓ 不承诺 provider 热备
✓ 不降低 QA gate
```

P0 适合作为第一批 PR；后续 Memory / Skill / E2B / Cache **不得**反过来要求 P0 重写。

---

# ADR 与实现决议

## ADR-01：Degraded Artifact Publishing — **Accepted**

**Decision：**

生成/构建成功时**可以**向用户暴露预览；但：

* **不得**合成 `qa_ok=true`（含静态 / deterministic smoke 冒充）
* **不得**自动正式发布
* 允许用户重试 QA / repair

用三个**相互独立**的标志表达，禁止用单一 `completed_degraded` 包揽：

```text
generation_success = true|false
previewable        = true|false
publishable        = false|true   # 未过正式 QA 门禁时必须为 false
```

硬原则：

> `previewable ≠ publishable`，`build_ok ≠ qa_ok`。

典型场景：

```text
代码生成成功 → build 成功 → 游戏可打开
→ Playwright / B 档 QA 未通过或不可执行

结果：
previewable=true
qa_ok 不得为 true
publishable=false
允许重试 QA / repair
```

---

## ADR-05：Recoverable Pause Representation — **Accepted**

**Decision：**

* P0 **不得**新增 `paused_recoverable`（或任何新的）`RunStatus` 枚举值
* 可恢复暂停复用现有 `paused`，用 `pause_reason` + `recovery` metadata 区分
* API consumer 只须理解：`running / paused / done / failed`

见 P0 §3。

---

## Context Builder（Implementation Decision，非 ADR）

> **P1 establishes Context Builder as the canonical memory/context composition path; P5 removes legacy prompt-assembly paths and enforces it as the sole production entry point.**

| Milestone | 职责 |
| --- | --- |
| **P1 MVP** | 出现统一 `ContextBuilder.build(...)`；负责 Session Summary、Recent Turns、Explicit Preferences、Current Artifacts、Current Request + token budget |
| **P5 Enforcement** | 所有正式 Node 禁止自行拼 Memory/历史；统一经 ContextBuilder；补 prompt fingerprint、skill/cache fingerprint、observability；删除遗留拼装路径 |

P1 若不建 Builder，Memory 会迅速分裂为 plan/art/code/repair 各自拼装。

---

## ADR-02：偏好删除策略 — Pending

删除 Game 时：

* **Explicit** 用户偏好（如「以后都像素风」）→ 默认保留在 User Memory
* **Inferred** 偏好若唯一 evidence 来自已删 Game → 删除或重算

用户「清除我的偏好」→ 删除 long-term preference（含派生检索索引，若已存在）

（P1 Explicit-only MVP 可先按「保留 explicit」落地；推断策略待本 ADR 定稿。）

---

## ADR-03：Sandbox Provider Strategy — **Pending**

**在决议前默认：**

```text
Domestic production → DockerSandbox
E2B → PoC / benchmark only
```

```text
E2B integration success ≠ E2B production approval
```

**不**在文档中默认允许国内源码/prompt/资产出境。Go 条件至少包括：数据流确认、源码/prompt/资产是否出境、供应商保留政策、合同/DPA/合规、国内网络 benchmark。

若最终「不允许 E2B」：SandboxBackend 抽象 + Docker 强化仍为**有效交付**，P3 不算失败。

评估维度：成本、可用区、国内网络、数据/源码出境、UGC 合规、SLA、冷启动、延迟、vendor lock-in。允许未来 hybrid，但须另决议。

---

## ADR-04：`forge_messages` 演进 — Pending

不得长期两套 Conversation Source of Truth。

* 方案 A：扩展现表（session_id / token_count / …）
* 方案 B：迁移到 `conversation_messages` + backfill

先审计现字段与调用点再选。

---

# P1：Memory MVP（Postgres only）

## P1 MVP

```text
Memory
├── Session Memory（演进 forge_messages）
└── User Preference（Postgres explicit only）
```

**不引入** Pinecone Preference / Conversation Vector（默认）。

### P1.1 Session Memory

逻辑：

```text
Game → Session（默认每 Game 一个主 Session）→ Messages
```

复用/演进 `forge_messages`，不平行新建 SoT。多 Session branch 不做。

### P1.2 Context Builder MVP（规范路径，非最终强制）

完整历史入库 ≠ 全量注入模型。

P1 **必须**引入统一入口，避免各节点自行拼装：

```python
ContextBuilder.build(
    node=...,
    current_input=...,
    session=...,
    preferences=...,
    artifacts=...,
)
```

第一阶段只负责：

```text
Session Summary
Recent Turns
Explicit Preferences
Current Artifacts
Current Request
+ token budget
```

Working memory 示例构成：

```text
Current Request
+ Recent N turns
+ Session Summary
+ Current Design Doc
+ Current Version Metadata
+ Relevant Preferences
```

Token budget 示例（后续用 trace 标定）：

```text
System / Policy        15%
Skills                 15%
Preferences             5%
Session summary        10%
Recent turns           20%
Artifacts              25%
Current request        10%
```

Memory 中的历史自然语言**永远是 data**，不得当作 instruction（防偏好/历史注入）。

遗留节点若暂未迁完，P1 允许并存但**新代码必须走 Builder**；P5 拆除遗留路径并强制唯一入口（见 P5）。

### P1.3 Session Summary

触发：`messages > N` 或 historical tokens > threshold（如 >20 条或 >12k tokens）。

结构化 schema 示例：

```json
{
  "current_goal": "",
  "confirmed_decisions": [],
  "rejected_options": [],
  "gameplay_constraints": [],
  "visual_constraints": [],
  "technical_constraints": [],
  "pending_requests": []
}
```

### P1.4 Preference MVP

表 `user_preferences`（字段可微调）：

```text
id, user_id, category, key, value_json
source, confidence, status
created_at, updated_at
```

MVP **仅自动写入 Explicit**（命中「以后 / 我喜欢 / 默认 / 每次都 / 不要再」等 + extractor schema 校验）。Inferred 后置。

### P1.5 Pinecone / 向量检索：暂缓

Explicit 偏好量级小，SQL 足够。Conversation semantic retrieval 仅当指标触发，例如：

* p95 session messages > 100，或
* summary 丢信息导致 revise failure > 约定阈值

再开独立子阶段（不叫默认 P1）。

## P1 Out-of-Scope

* Preference → Pinecone
* 跨 Game 隐式画像大规模推断
* 多 Session 分支
* 用 Memory 替代 `run_checkpoints`

## P1 Go / No-Go

* Game A 对话不泄漏到 Game B
* 上下文长度不随消息线性失控（有 budget）
* Explicit 偏好可查看 / 修改 / 清空
* 删 Game 后 Session 不可检索；User explicit 偏好按 ADR-02
* 仅一套 message SoT
* 新节点/新调用路径经 `ContextBuilder`；无「第四套」私有拼装

---

# P2：Agent Skills（Policy ≠ Methodology）

代码层面建议命名：

```text
Platform Policy   # 强制
Agent Skills      # 可选方法论
```

避免两者权限被当成同一概念。

## P2.1 Platform Policy（强制注入 / 代码权威）

包括：Security、CDN 白名单、引擎钉死 URL、输出契约、网络规则、审核、沙箱限制、**QA 最低门禁（B 档 Playwright）** 等。

Agent **无权**选择、跳过、卸载或覆盖。例如 Phaser CDN URL 来自 `ALLOWED_CDN_HOSTS` / `recommended_cdn_url`，不是 Skill「建议」。

## P2.2 Methodology Skill（可发现、可选）

如 `art/pixel-art`、`code/phaser3`、`repair/runtime-error`。流程：discover → choose → load（Progressive Disclosure；符合 Agent Skills `SKILL.md` 惯例）。

## P2.3 Skill MVP（约 8 个，验证质量 lift）

```text
Art: pixel-art, hud-design, visual-composition
Code: canvas, phaser3, pixijs
Repair: runtime-error, gameplay-regression
```

目标：验证 routing 是否优于静态全量注入，**不是**一次性重写全部 prompt。

## P2.4 分层 Routing

```text
Node Type → Platform Scope Filter → metadata catalog → Agent select → Loader
```

Art 不得看见 billing / sandbox admin / 内部 security runbook。

## P2.5 playtest 拆分

| 概念 | 类型 | 含义 |
| --- | --- | --- |
| playtest-policy | Platform Policy | 必须过 B 档 Playwright；不可静态假通过 |
| playtest-methodology | Skill | 如何观察输入、运动弱信号、报告证据（给诊断/修复提示） |

现有 `playtest.md` / `conventions.md` 按此拆分演进。

## P2 Out-of-Scope

* 几十上百 Skill 大目录
* Agent 自选是否执行 QA 门禁
* 开放 tool-use / ReAct harness

## P2 Go / No-Go

* 节点启动不加载全部 Skill 正文
* Policy 始终注入；Methodology 可选
* Skill 变更使依赖其的 cache key 失效（若已上 Exact Cache）
* 离线 eval：selection precision / quality lift；无 lift 则停扩 catalog

**本仓库**：`forge/skills/offline_eval.py` + `tests/test_skills_offline_eval.py`（≥12 fixtures；precision@1 / member hit / vs 全量注入 body reduction；Art 跨域违规=0）。真实 LLM A/B quality-lift 仍 gated。

---

# P3：Sandbox Backend 评估与抽象（非「立刻切 E2B」）

阶段名称：**Sandbox Backend Evaluation & Abstraction**。

受 **ADR-03 Pending** 约束：国内生产默认 Docker；E2B 仅 PoC/benchmark，**不得**因集成成功而默认生产切换或默认允许源码出境。

## P3 MVP

```python
class SandboxBackend(Protocol):
    async def create(...)
    async def execute(...)
    async def destroy(...)
```

第一版不强制 pause/snapshot。Adapter：

* `LocalSandbox`（开发）
* `DockerSandbox`（生产基线）
* `E2BSandbox`（PoC）

Feature flag：`sandbox_backend=local|docker|e2b`。

**职责边界**：

| 能力 | 默认位置 |
| --- | --- |
| 源码 execute / 构建命令 | Sandbox Backend |
| B 档 Playwright 冒烟 | Worker 侧 Playwright（可与 sandbox 分离） |
| Vite Builder | 现有 builder；不强行并入 E2B |

HITL 长等待（可达 `hil_wait_timeout_s`）下：**默认销毁 sandbox，只保留对象存储/托管中的源码与 checkpoint**；用户回来再 create + restore。不默认 48h pause 计费会话。

## P3.1 Benchmark

样本量级建议：Canvas/Phaser/Pixi/Vite/Repair 对照集。指标：create/build/exec latency、OOM/timeout/failure、cost/run、cost/成功局、网络可靠性；区分国内外。

## P3.2 数据合规 Gate

Prompt、design_doc、源码、素材是否出境 → Data Flow Diagram → 才能谈默认 backend。

## P3.3 Tier

候选 lite/standard/heavy（或四档）；以 telemetry 为准，避免为省几十 MB 过度调度。

**本仓库 MVP**：`sandbox/tiers.py` + Docker `lite` 档；`sandbox_tier_auto`（默认关）时 OneShot 按源码体量 / engine hint / 近期 OOM·超时 推荐；Prometheus `gameforge_sandbox_tier_executions_total`；进程内环形缓冲非跨实例 SoT。

## P3.4 复用

允许：同 Run、同 CodeQaLoop 内复用。禁止：跨 Run / 跨用户。PoC 可先 one-run-one-sandbox。

## P3 Go / No-Go（生产切换）

同时满足才可默认 E2B，否则 **Docker 继续作为生产 Backend 是合法结果**：

* 可靠性 ≥ Docker baseline
* 成本在预算内
* p95 latency 可接受
* 数据合规通过
* 国内网络策略明确
* rollback 可行
* sandbox leak = 0（实验窗口内）

---

# P4：Cache（先 Exact，Semantic 实验后置）

## P4 MVP：Redis Exact Cache 白名单

允许：

```text
entry_router / engine_router
intent classification
deterministic metadata extraction
template selection
```

特点：低熵、结构化、temperature≈0。

**禁止** Exact 与 Semantic：

```text
plan / art / code / repair / qa
preference extraction / HITL revise
```

理由：创作与修复路径随机性高；Exact 命中也会固化「碰巧可跑的差版本」。

### Cache Key

```text
node, input_hash, model, prompt_version, policy_version, skill_bundle_hash
```

`preference_revision` **仅当**该节点实际消费 Preference 时加入。

## P4.5 Semantic Cache（实验，非默认）

前置：Exact 已证明有成本/延迟收益。

* 仅 router/classification
* **Shadow mode**：生产仍走真实推理；后台记 similarity vs 真实输出，标定 `T_direct` / `T_verify`
* 未完成 calibration 与 false-hit 验收前，**禁止 direct hit 返回用户**
* 默认禁止跨用户；Pinecone 与 Memory 逻辑空间分离（若引入）

灰度：shadow → 5% → 20% → 50% → 100%。

## P4 Go / No-Go

* allowlist 外 0 缓存命中
* Code/Repair/Art 无 cache
* Semantic false direct-hit 目标（若上线）极高 precision（如 <0.1%），否则不下发

**MVP 验收（本仓库）**：`exact_cache_enabled` 默认开；`test_exact_cache.py` 覆盖禁止节点不写 Redis、白名单 roundtrip、flag 关闭、entry/engine/template 包装；`create_run` / `GET /templates` / `create_game(template_id)` 已接线。P4.5 Semantic 仍实验未开。

---

# P5：整合与硬化（不加核心子系统）

* **Context Builder Enforcement**：所有正式 Node 禁止自行拼 Memory/加载历史；统一经 ContextBuilder；删除遗留 prompt-assembly；补 prompt / skill / cache fingerprint 与 observability
* Observability：Memory / Skill / Sandbox / Cache span（Langfuse 等）
* Migration cleanup、Feature flag 收敛、废弃路径删除
* Chaos / Load / Security 测试
* 文档与 ADR 归档

**MVP 进度（本仓库）**：plan/art/art_detail/code|repair/diagnose **唯一**经 `build_node_context`（遗留 concat 双路径已删）；`BuiltContext.fingerprint` + spans；Art/QA Methodology；`test_legacy_concat_removed.py` 守门。`memory_context_builder` 仅控制是否注入 recent turns。P4.5 Semantic、E2B 生产切换、真实 LLM A/B、全量 Load 仍 gated。

---

# 现有模块 → 新架构映射

| 现有模块 | 新架构位置 | 处理方式 |
| --- | --- | --- |
| `entry_router` | Routing | 保留；加 timeout；可进 Exact Cache |
| `plan` / `art` 节点 | Agent Node | 保留结构；后接 Methodology Skill |
| `code_qa_loop` | Reliability + Agent Loop | **核心保留，不重写** |
| `code_qa_exec` / `code_candidate` | Artifact / Loop 执行 | 保留；增强幂等与 metadata |
| `design_doc` | Session Artifact | 保留；进 Context Builder |
| `current_version` / hosting | Durable Artifact | 保留；repair SoT |
| `forge_messages` | Session Memory | 演进/迁移，不平行重建 |
| `run_checkpoints` + Redis ckpt | Reliability | 保留；增强恢复 metadata；不强制迁 LangGraph checkpointer（除非另立 ADR） |
| Redis `run:executing` | Lease | 保留，不重复实现 |
| Redis usage / ratelimit / circuit | Infra / Policy | 原样保留 |
| blacklist / lexicon / audit | Platform Policy | 保留 |
| Playwright playtest | Platform QA Gate | 保留硬门禁 |
| `playtest.md` / `conventions.md` | Policy + Skill | 拆分演进 |
| engines/*.md | Methodology Skills | 标准化 SKILL.md |
| LocalSandbox / DockerSandbox | Sandbox Backend | 开发 / 生产基线；E2B 为对照 |
| Vite Builder | Build Runtime | 不强行并入 E2B |
| Langfuse | Observability | 保留并扩展 span |

原则：**能复用的不重写。**

---

# 阶段总表

| Priority | MVP | 完整增强（需 Go） |
| --- | --- | --- |
| **P0 Reliability** | 错误分类、node timeout、`paused`+`pause_reason`、幂等 | 高级 reconciler、复杂 fallback |
| **P1 Memory** | forge_messages 演进、summary、PG explicit preference、**Context Builder MVP** | inferred preference、conversation vector retrieval |
| **P2 Skills** | Policy/Methodology 分层、≈8 Skill、Router | 大规模 catalog |
| **P3 Sandbox** | Backend 抽象 + E2B PoC + benchmark（ADR-03 Pending） | 按 ADR-03 选 E2B / Docker / hybrid |
| **P4 Cache** | Redis Exact 白名单 | Semantic shadow → 灰度 |
| **P5 Hardening** | **Context Builder Enforcement**、测试、清理 | 删除 legacy |

统一推进节奏：

```text
MVP → Feature Flag / Shadow → Metrics → Review → Go/No-Go → 扩大范围
```

---

# 架构验收红线

1. **Sandbox 不是状态存储。** 随时可杀，Run 仍可从持久化源恢复。
2. **Memory 不是全量 Prompt History。** 完整保存，注入受 Context Builder 约束。
3. **Semantic similarity ≠ 业务等价。** 未标定禁止 direct hit。
4. **Skill 可发现、可选、可版本化；Policy 不可选。** 禁止退化成「几十个 md 全塞 prompt」。
5. **Node Failure ≠ Run Failure。** 可恢复故障必须被 retry / fallback / `paused`+`pause_reason=recoverable_error` 吸收。
6. **CodeQaLoop B 档硬门禁不可削弱。** 静态检测不得成为生产 `qa_ok`；`previewable ≠ publishable`，`build_ok ≠ qa_ok`。

### 范围控制

每一 P：MVP、Out-of-Scope、Flag、Rollback、Go/No-Go；禁止因「最终架构需要」提前实现后续模块。

### Migration

* 单一 Conversation SoT；`forge_messages` 有兼容/backfill 计划
* 滚动发布期间旧 Run 可恢复；老游戏历史不因 Memory 升级丢失

### Sandbox

E2B 是否进生产以 **ADR-03** 与对照指标/合规为准；在 Pending 期间国内生产保持 Docker。Docker 继续生产是合法结局。

---

## 修订说明（相对 v1 / 早期 v2 草稿）

| 倾向 | 现行决议 |
| --- | --- |
| 目标态一次性 Runtime 替换 | 增量演进 + 每阶段 Go/No-Go |
| 大状态机 / 新 `paused_recoverable` status | **ADR-05 Accepted**：`paused` + `pause_reason`；P0 不改 RunStatus |
| `completed_degraded` 包揽语义 | **ADR-01 Accepted**：`generation_success` / `previewable` / `publishable` 三分立 |
| Playwright → 静态 QA fallback | **禁止**；对齐 CodeQaLoop |
| Pinecone 默认进 Memory | 暂缓；指标触发 |
| 直接 E2B 迁移 / 默认允许国内出境 | **ADR-03 Pending**；生产 Docker；E2B 仅 PoC |
| Semantic Cache 猜阈值 | Exact 先行；Semantic 仅 shadow |
| Skill 全量方法论 | Policy 强制 / Methodology 可选；≈8 个验证 |
| Context Builder 二选一里程碑 | **P1 MVP + P5 Enforcement** |
| 「无需拍板即可开工」 | ADR-01/05 已 Accepted；02/03/04 仍按阶段阻塞 |

---

## 文档与命名

* 规范文件名：`docs/2026-08-15-forge-runtime-evolution-plan.md`
* 正文使用 specification 语气，避免对话体
* 可恢复故障的正式表述：

> 系统必须保证可恢复的基础设施与模型瞬态故障不会直接导致 Run 进入不可恢复终态；数据完整性破坏、安全违规与系统 invariant 破坏除外。
