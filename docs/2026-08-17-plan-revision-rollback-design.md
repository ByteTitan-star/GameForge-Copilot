# GameForge 跨阶段策划修订与失败恢复生产级技术方案

* **Status:** Proposed
* **Date:** 2026-08-18
* **Owners:** TBD
* **Scope:** Workflow Recovery / Replan / Artifact Lineage
* **核心目标:** 在不重写现有 LangGraph + PostgreSQL + RabbitMQ 工作流骨架的前提下，使后置开发/QA 阶段能够基于真实失败证据安全地修订上游策划，并保证恢复流程具备生产级的一致性、幂等性、可审计性和版本兼容能力。

---

## 目录

1. 背景与现状
2. 问题定义
3. 已确认的现有基础设施
4. 架构目标与设计原则
5. 核心领域模型
6. RunCommand
7. HITL 控制版本与陈旧请求防护
8. FailureReport
9. FailureClass 判定机制
10. RecoveryPolicy
11. PlanRevision 与 Artifact Lineage
12. Art 失效与复用策略
13. Promotion Guard
14. Capability Validation
15. Acceptance Contract
16. REVISE_PLAN 执行流程
17. 消息可靠性与 Command 幂等
18. Cancel / Pause / Resume 收敛
19. Workflow Versioning
20. Prompt 与失败证据安全
21. Budget 与成本控制
22. API / WebSocket / Frontend Contract
23. 可观测性与审计
24. 数据模型
25. 分阶段实施计划
26. 测试与验收
27. Rollout 与回滚
28. Non-Goals
29. 最终架构不变量
30. 最终决策

---

# 1. 背景与现状

GameForge 当前工作流大致为：

```text
User Idea
   │
   ▼
Plan
   │
   ▼
Plan Confirm
   │
   ▼
Art
   │
   ▼
Art Confirm
   │
   ▼
Code
   │
   ▼
Sandbox / Playtest / QA
   │
   ▼
Done
```

主要技术组件：

```text
FastAPI
LangGraph
PostgreSQL
Redis
RabbitMQ
Cloud Sandbox
Playwright
WebSocket
```

当前采用：

> **单步 Workflow 执行 + PostgreSQL 状态持久化 + 外部 HITL 暂停恢复 + RabbitMQ 异步调度 + 集中式 route_start**

模型。

典型 HITL：

```text
Node
 ↓
_pause_hitl()
 ↓
Run PAUSED
 ↓
Graph END
 ↓
User Decision
 ↓
enqueue_resume
 ↓
RabbitMQ
 ↓
Worker
 ↓
route_start()
 ↓
Next Node
```

本方案不改变这一核心执行模型。

---

# 2. 问题定义

当前系统隐含一个不成立的业务假设：

> Plan 一旦确认，后面的 Code / QA 只能修改实现，不能重新审视 Plan。

现实中，开发和 QA 同时承担：

1. Implementation Verification
2. Developability Verification

某些策划只有真正进入：

* Build
* Runtime
* Browser Playtest
* Resource Measurement
* Automated QA

之后，才能确认其不可实现或不经济。

例如：

```text
3D 开放世界
+
实时多人同步
+
复杂物理
+
大量动态资产
```

策划本身可能语义合理，但超出当前 Runtime 能力。

如果继续：

```text
Code Retry 1
 ↓
Code Retry 2
 ↓
Code Retry 3
```

并不能解决问题。

真正需要的是：

```text
Plan P1
 ↓
失败证据 F1
 ↓
用户确认修改
 ↓
Plan P2
```

因此本方案正式把问题定义为：

> **Cross-stage Replan & Recovery**

而不是简单的：

> Plan Rollback

---

# 3. 已确认的现有基础设施

本方案必须基于当前代码事实，而不是重新设计已经存在的基础设施。

## 3.1 Transactional Outbox 已存在

现有代码已经具备 Task Outbox：

```text
app/messaging/outbox.py
```

其中 `add_task` 在业务数据库事务内写入 `TaskOutbox`。

当前：

```text
app/forge/queue.py
```

中的 `enqueue_resume` 已经保证：

```text
resume_grant write
+
add_task()
+
DB COMMIT
```

位于同一 PostgreSQL Transaction 内。

因此以下经典故障：

```text
DB commit success
RabbitMQ publish failure
```

不会导致 Resume 永久丢失。

Publish 失败后 TaskOutbox 记录仍然存在。

---

## 3.2 Outbox Publisher 已存在

现有：

```text
dispatch_pending
```

已经负责：

```text
TaskOutbox
 ↓
RabbitMQ Publish
 ↓
Retry
```

并具有：

* retry
* exponential backoff
* `skip_locked`
* 并发 publisher 防重
* 最终失败处理

因此：

> **本方案不新建 `outbox_events`。**

统一复用现有：

```text
task_outbox
```

---

## 3.3 Worker 租约恢复已存在

现有 Scheduler 已有：

```text
RUNNING lease lost recovery
```

因此 Worker 死亡后的基础任务回收机制已经存在。

本方案不重复实现。

---

## 3.4 当前消息层真正缺少的能力

现有消息可靠性主要解决：

```text
Task 不丢
```

但还没有正式解决：

```text
同一个业务 Command 被重复消费时，
是否只产生一次业务效果
```

因此本方案消息层真实增量只有：

```text
RunCommand identity
+
command_id
+
command execution status
+
worker-side command idempotency
```

而不是重建 Outbox。

---

# 4. 架构目标与设计原则

## 4.1 历史只能向前

禁止：

```text
P1 → overwrite → P2
```

应使用：

```text
P1
 ↓
P2
```

其中 P1 永远保留。

同理：

```text
Art A1
Candidate C1
Failure F1
```

不能因为新版本产生而删除。

---

## 4.2 Replan 不是 Rollback

业务含义：

```text
PlanRevision P1
   │
   ▼
ArtRevision A1
   │
   ▼
CandidateRevision C1
   │
   ▼
FailureReport F1
   │
   ▼
REVISE_PLAN
   │
   ▼
PlanRevision P2
```

系统并没有回到 P1。

而是基于 P1 + F1 创建 P2。

---

## 4.3 失败类别与 Workflow Phase 解耦

禁止长期使用：

```text
qa_failed → 某恢复动作
sandbox_failed → 某恢复动作
```

作为核心恢复模型。

改为：

```text
Observed Failure
 ↓
Failure Classification
 ↓
RecoveryPolicy
 ↓
Allowed Commands
```

---

## 4.4 用户语义变化需要 HITL

以下操作改变产品语义：

```text
3D → 2D
多人 → 单人
开放地图 → 有限地图
删除机制
缩减关卡
修改核心验收标准
```

必须用户确认。

基础设施恢复：

```text
503
RabbitMQ redelivery
Sandbox startup timeout
临时网络失败
```

不需要用户做产品决策。

---

## 4.5 消息允许重复，业务效果不能重复

系统目标明确为：

```text
At-Least-Once Delivery
+
Exactly-Once Business Effect
```

不追求依赖 Broker 实现虚假的：

```text
Exactly-Once Delivery
```

---

## 4.6 在昂贵阶段之前尽早失败

优先：

```text
Plan
 ↓
Developability Validation
 ↓
Plan Confirm
```

而不是：

```text
Plan
 ↓
Art
 ↓
Code × N
 ↓
最终才知道根本做不了
```

---

# 5. 核心领域模型

本次架构正式引入四个核心概念：

```text
RunCommand
FailureReport
Artifact Revision
Artifact Lineage
```

另外增加两个控制能力：

```text
control_revision
workflow_version
```

最终逻辑模型：

```text
Run
 │
 ├── RunCommand
 │
 ├── FailureReport
 │
 └── ArtifactRevision
        │
        ├── PlanRevision
        ├── ArtRevision
        └── CandidateRevision
```

本期 **不独立创建 QAContractRevision**，Acceptance Contract 作为 PlanRevision 的结构化组成部分，后文详述。

---

# 6. RunCommand

## 6.1 为什么引入 Command

当前 HITL vocabulary 存在：

```text
approve
modify
select_a
select_b
```

其中：

```text
qa_failed + approve
```

实际表示：

```text
重新尝试实现
```

离开 `phase` 后：

```text
approve
```

无法表达任何完整业务语义。

因此内部领域模型统一改为具有明确语义的 Command。

---

## 6.2 Command 类型

建议：

```python
class RunCommandType(StrEnum):
    APPROVE_PLAN = "approve_plan"
    REVISE_PLAN = "revise_plan"

    SELECT_ART_A = "select_art_a"
    SELECT_ART_B = "select_art_b"
    REVISE_ART = "revise_art"

    RETRY_IMPLEMENTATION = "retry_implementation"
    RETRY_INFRA = "retry_infra"

    CANCEL_RUN = "cancel_run"
```

未来如有需要可以扩展：

```text
CHANGE_RUNTIME
ACCEPT_DEGRADED_RESULT
RESTART_FROM_ART
```

本期不实现。

---

## 6.3 Legacy Decision Adapter

迁移期外部 API 可以暂时接受旧 vocabulary。

但必须在统一边界转换。

示例：

```python
LEGACY_DECISION_MAP = {
    ("plan_confirm", "approve"):
        RunCommandType.APPROVE_PLAN,

    ("plan_confirm", "modify"):
        RunCommandType.REVISE_PLAN,

    ("qa_failed", "approve"):
        RunCommandType.RETRY_IMPLEMENTATION,

    ("qa_failed", "modify"):
        RunCommandType.RETRY_IMPLEMENTATION,

    ("sandbox_failed", "approve"):
        RunCommandType.RETRY_IMPLEMENTATION,

    ("sandbox_failed", "modify"):
        RunCommandType.RETRY_IMPLEMENTATION,
}
```

对于：

```text
modify
```

原始 `modify_text` 转入：

```text
command.payload.feedback
```

---

## 6.4 Adapter 必须覆盖所有 Resume 入口

当前 Resume 不只来自：

```text
resolve_hitl
```

还包括：

```text
resolve_hitl
resume_run_control
retry_run
dev_requeue
```

因此禁止在各入口分别手写 legacy mapping。

应增加统一函数，例如：

```python
normalize_resume_command(...)
```

所有进入：

```text
enqueue_resume
```

之前的路径统一调用。

原则：

> **Command Normalization 必须发生在公共 Resume Boundary，而不是某一个 API Endpoint。**

否则会出现部分路径：

```text
有 command_id
```

部分路径：

```text
只有 legacy resume_grant
```

的问题。

---

# 7. HITL 控制版本与陈旧请求防护

## 7.1 不复用 RunCheckpoint revision

当前 RunCheckpoint 上已有 revision / version 类概念。

但它解决的是：

> Workflow State 是否被其他写操作修改。

用户 HITL 需要解决的是：

> 用户当前看到的决策页面是否仍然有效。

这两个概念语义不同。

因此不复用 Checkpoint Revision。

---

## 7.2 新增 runs.control_revision

在 `runs` 表增加：

```text
control_revision BIGINT NOT NULL DEFAULT 0
```

它只表达：

> 对外可操作控制状态的版本。

例如以下行为会递增：

```text
进入新的 HITL
Resolve HITL
Cancel
Resume
会导致旧用户操作失效的控制状态变更
```

普通内部：

```text
token usage update
metric update
worker heartbeat
```

不递增。

---

## 7.3 HITL Payload

向客户端发送：

```json
{
  "decision_id": "decision_xxx",
  "control_revision": 42,
  "allowed_commands": [
    "retry_implementation",
    "revise_plan",
    "cancel_run"
  ]
}
```

---

## 7.4 Resolve CAS

客户端提交：

```json
{
  "decision_id": "decision_xxx",
  "expected_control_revision": 42,
  "command": "revise_plan",
  "feedback": "改成 2D"
}
```

服务器：

```sql
UPDATE runs
SET control_revision = control_revision + 1
WHERE id = :run_id
  AND control_revision = :expected_control_revision;
```

如果：

```text
affected rows != 1
```

返回：

```text
409 STALE_DECISION
```

---

## 7.5 解决的问题

这一机制直接解决：

```text
双击按钮
两个浏览器 Tab
旧 WebSocket UI
重复 HTTP 请求
用户在 Run 已恢复后再次点击旧决策
```

---

# 8. FailureReport

## 8.1 Failure 必须在暂停前冻结

禁止：

```text
进入 REVISE_PLAN
 ↓
临时读取“当前 checkpoint 的错误”
```

因为错误上下文可能已经发生变化。

正确流程：

```text
Failure occurs
 ↓
Create FailureReport
 ↓
Persist
 ↓
Create HITL
 ↓
PAUSE
```

---

## 8.2 FailureReport 建议结构

```json
{
  "id": "failure_123",
  "run_id": "run_1",

  "plan_revision_id": "plan_3",
  "art_revision_id": "art_2",
  "candidate_revision_id": "candidate_8",

  "failure_class": "CAPABILITY_MISMATCH",
  "classification_source": "CAPABILITY_VALIDATOR",
  "classification_confidence": 1.0,

  "failure_stage": "PLAYTEST",

  "attempt_count": 3,

  "attempts": [
    {
      "attempt": 1,
      "stage": "build",
      "error_code": "BUILD_ERROR",
      "summary": "..."
    },
    {
      "attempt": 2,
      "stage": "runtime",
      "error_code": "RUNTIME_ERROR",
      "summary": "..."
    }
  ],

  "diagnosis": {
    "summary": "...",
    "suggested_recovery": "REVISE_PLAN"
  },

  "resource_usage": {
    "sandbox_seconds": 83,
    "llm_tokens": 12000
  },

  "created_at": "..."
}
```

---

## 8.3 FailureReport 不可变

创建后不覆盖：

```text
F1
```

如之后产生新错误：

```text
F2
```

不能更新 F1。

这样能够稳定回答：

> 用户当时为什么看到“建议修改策划”？

---

# 9. FailureClass 判定机制

FailureClass 不能单纯交给 LLM 自由判断。

这是 Recovery 模型中最关键的安全边界之一。

采用：

> **Deterministic First + Validator Second + LLM Assisted Fallback + UNKNOWN Conservative Path**

---

## 9.1 FailureClass

```python
class FailureClass(StrEnum):
    INFRA_TRANSIENT = "infra_transient"
    IMPLEMENTATION_DEFECT = "implementation_defect"
    CAPABILITY_MISMATCH = "capability_mismatch"
    ACCEPTANCE_MISMATCH = "acceptance_mismatch"
    RESOURCE_EXCEEDED = "resource_exceeded"
    POLICY_SECURITY = "policy_security"
    UNKNOWN = "unknown"
```

---

## 9.2 第一层：确定性规则

结构化基础设施信号优先。

例如：

```text
HTTP 502 / 503 from sandbox control plane
sandbox allocation timeout
browser launch infrastructure error
RabbitMQ transport failure
```

直接：

```text
INFRA_TRANSIENT
```

例如：

```text
TypeScript compiler error
ReferenceError
module resolution caused by generated source
```

优先：

```text
IMPLEMENTATION_DEFECT
```

例如：

```text
memory hard limit
bundle size hard limit
sandbox execution quota
```

直接：

```text
RESOURCE_EXCEEDED
```

Policy Engine 明确拒绝：

```text
POLICY_SECURITY
```

这些硬规则不能被 LLM 覆盖。

---

## 9.3 第二层：Capability Validator

若当前 Plan 声明：

```text
realtime_multiplayer = true
```

但 Runtime CapabilityProfile：

```text
realtime_multiplayer = false
```

则确定性得到：

```text
CAPABILITY_MISMATCH
```

这类结果：

```text
classification_source = CAPABILITY_VALIDATOR
classification_confidence = 1.0
```

---

## 9.4 第三层：LLM Assisted Diagnosis

只有无法通过结构化规则确定时，才允许 LLM 对以下问题做辅助诊断：

```text
IMPLEMENTATION_DEFECT
vs
ACCEPTANCE_MISMATCH
vs
suspected CAPABILITY_MISMATCH
vs
UNKNOWN
```

LLM 输入必须是结构化、清洗后的 Failure Evidence。

LLM 输出必须是 Schema：

```json
{
  "candidate_class": "ACCEPTANCE_MISMATCH",
  "evidence": [],
  "reason": "..."
}
```

---

## 9.5 不信任 LLM 自报 confidence

禁止直接采用：

```json
{
  "confidence": 0.93
}
```

作为安全决策依据。

`classification_confidence` 必须由系统依据：

```text
rule strength
validator result
evidence coverage
signal consistency
```

计算。

---

## 9.6 UNKNOWN 保守策略

证据不足或者冲突时：

```text
UNKNOWN
```

禁止为了“必须分到某一类”而强行分类。

UNKNOWN 默认：

```text
不自动修改任何用户语义
```

进入通用恢复 UI：

```text
再次尝试
修改策划
取消
```

但 UI 不显示：

> 系统确认策划不可实现

这类强结论。

---

## 9.7 分类监控

新增：

```text
forge_failure_class_total
forge_failure_class_unknown_total
forge_failure_class_override_total
forge_failure_recovery_mismatch_total
```

如果未来允许用户：

```text
“这不是策划问题”
```

显式纠正诊断，则记录：

```text
forge_failure_class_user_corrected_total
```

这将成为后续优化分类器的重要数据。

---

# 10. RecoveryPolicy

FailureClass 与恢复策略单独建模。

| FailureClass            | 默认恢复                    | 是否 HITL     |
| ----------------------- | ----------------------- | ----------- |
| `INFRA_TRANSIENT`       | `RETRY_INFRA`           | 否           |
| `IMPLEMENTATION_DEFECT` | 自动 Code Repair          | Budget 耗尽后是 |
| `CAPABILITY_MISMATCH`   | 推荐 `REVISE_PLAN`        | 是           |
| `ACCEPTANCE_MISMATCH`   | 推荐 `REVISE_PLAN`        | 是           |
| `RESOURCE_EXCEEDED`     | Replan / Retry / Cancel | 是           |
| `POLICY_SECURITY`       | 必须调整 Plan 或 Cancel      | 是           |
| `UNKNOWN`               | Retry / Replan / Cancel | 是           |

核心逻辑从：

```text
phase → action
```

改为：

```text
failure_class
+
retry_budget
+
runtime_context
 ↓
RecoveryPolicy
 ↓
allowed_commands
```

### RETRY_INFRA 与图内 infra_replay 的边界

CodeQaLoop 现有图内 `infra_replay` 环（attempt +1、同 Candidate 重放）**保留不动**，
它负责执行过程中的自动 infra 重试。

`RETRY_INFRA` 命令只用于一个场景：

```text
Run 已经因 infra 原因暂停（如 infra retry budget 耗尽进入 HITL）
 ↓
用户 / 系统恢复执行
```

即：图内环管执行中，命令管恢复时。二者不是替代关系，禁止在引入命令式恢复时删除图内 `infra_replay`。

---

# 11. PlanRevision 与 Artifact Lineage

## 11.1 不可变 Revision

生产模型：

```text
PlanRevision P1
PlanRevision P2

ArtRevision A1
ArtRevision A2

CandidateRevision C1
CandidateRevision C2
```

禁止：

```text
design_doc = new_value
```

覆盖全部历史语义。

---

## 11.2 PlanRevision

建议：

```json
{
  "id": "plan_4",
  "run_id": "run_1",
  "revision": 4,

  "supersedes": "plan_3",

  "schema_version": 2,

  "payload_uri": "...",
  "payload_hash": "...",

  "created_by_command_id": "cmd_123",

  "created_at": "..."
}
```

---

## 11.3 ArtRevision

```json
{
  "id": "art_5",
  "run_id": "run_1",

  "plan_revision_id": "plan_4",

  "dependency_fingerprint": "...",

  "status": "ACTIVE"
}
```

---

## 11.4 CandidateRevision

```json
{
  "id": "candidate_12",

  "run_id": "run_1",

  "plan_revision_id": "plan_4",
  "art_revision_id": "art_5",

  "status": "ACTIVE",
  "qa_status": "PASSED"
}
```

---

# 12. Art 失效与复用策略

只在本节定义一次，其他章节不重复定义。

## 12.1 P0 默认策略

Plan Revision 改变后：

```text
P1 → P2
```

默认：

```text
A1 → STALE
C1 → STALE
```

重新生成 Art。

原因：

> 正确性优先于成本优化。

---

## 12.2 P1 优化：Dependency Fingerprint

后续允许判断：

```text
Plan 改动是否实际影响 Art
```

例如 Art 依赖：

```text
visual_style
color_palette
entity_visual_description
ui_visual_structure
environment_style
animation_requirements
asset_needs
```

生成：

```text
art dependency projection
 ↓
canonical serialization
 ↓
SHA-256
```

---

## 12.3 Canonicalization 必须钉死

Fingerprint 协议必须有版本，例如：

```text
art-dependency-fingerprint-v1
```

Canonicalization 规则：

```text
Unicode normalization = NFC

JSON object keys = lexical sorted

encoding = UTF-8

whitespace = none

JSON separators = fixed

null representation = fixed

number serialization = fixed
```

数组：

> 默认保留顺序。

只有字段 Schema 明确声明：

```text
semantic set
```

时，才允许排序后 Hash。

禁止通用地对所有数组排序。

否则：

```text
关卡 1, 2, 3
```

和：

```text
关卡 3, 2, 1
```

可能被错误认为相同。

---

## 12.4 Fingerprint 协议升级

如果 Dependency Projection Schema 变化：

```text
v1 → v2
```

禁止直接比较不同版本 Hash。

必须：

```text
fingerprint_version == same
```

才能复用。

---

# 13. Promotion Guard

旧 Candidate 不删除。

Plan 改动后：

```text
active_candidate_revision_id = null
```

同时：

```text
C1.status = STALE
C1.stale_reason = PLAN_SUPERSEDED
```

任何 Promote 前执行最终 invariant：

```python
candidate.plan_revision_id == run.active_plan_revision_id

candidate.art_revision_id == run.active_art_revision_id

candidate.status == ACTIVE

candidate.qa_status == PASSED
```

P1 Art Fingerprint 上线以后再增加：

```text
candidate dependency compatibility == true
```

任一失败：

```text
PROMOTION_REJECTED_STALE_ARTIFACT
```

Promotion Guard 是最后一道安全边界。

不能假设：

> 前面的 route 应该已经做对了。

---

# 14. Capability Validation

禁止使用：

```text
"3D"
"物理引擎"
"网络同步"
```

关键词黑名单判断 Plan 是否可实现。

---

## 14.1 CapabilityProfile

平台维护：

```json
{
  "profile_version": "2026-08-18.1",

  "renderers": [
    "dom",
    "canvas2d",
    "phaser2d",
    "pixijs"
  ],

  "webgl_3d": false,
  "physics_2d": true,
  "realtime_multiplayer": false,
  "backend_server": false,

  "limits": {
    "max_build_seconds": 120,
    "max_bundle_mb": 30,
    "max_asset_count": 80
  }
}
```

---

## 14.2 RequiredCapabilities 直接进入 Design Doc Schema

不增加单独一次：

```text
LLM capability extraction
```

调用。

Plan Agent 一次性输出：

```json
{
  "title": "...",

  "required_capabilities": {
    "renderer": "canvas2d",
    "physics_2d": true,
    "realtime_multiplayer": false,
    "backend_server": false
  },

  "acceptance_contract": [],

  "..."
}
```

优点：

```text
少一次模型调用
减少信息重复
降低漂移
Schema 单一来源
```

---

## 14.3 Deterministic Capability Validator

执行：

```text
design_doc.required_capabilities
       ×
CapabilityProfile
       ↓
CapabilityValidator
```

明确不支持：

```text
CAPABILITY_MISMATCH
```

---

## 14.4 Developability Precheck

推荐：

```text
Plan Generation
 ↓
Schema Validation
 ↓
Capability Validation
 ↓
Budget Validation
 ↓
Acceptance Validation
 ↓
Plan Confirm
```

明显不可实现的问题尽量不进入 Art / Code。

---

# 15. Acceptance Contract

本方案取消独立：

```text
QAContractRevision
```

Artifact。

原因：

1. 当前 Acceptance Criteria 本质属于 Plan；
2. Plan Revision 改变后 QA Contract 必然一起改变；
3. 独立 Artifact 会制造新的双版本一致性问题；
4. 当前没有独立生命周期需求。

因此结构化为：

```text
PlanRevision.acceptance_contract
```

---

## 15.1 示例

```json
{
  "acceptance_contract": [
    {
      "id": "AC-01",
      "description": "玩家可以通过方向键移动",
      "severity": "BLOCKER",
      "testability": "AUTOMATED",
      "strategy": "PLAYWRIGHT"
    },
    {
      "id": "AC-02",
      "description": "整体视觉保持轻松风格",
      "severity": "NON_BLOCKER",
      "testability": "LLM_REVIEW"
    }
  ]
}
```

---

## 15.2 未来拆分条件

只有当未来出现以下需求时再单独 ADR：

```text
同一 Plan 多套 QA Profile
QA Contract 独立人工编辑
不同 Runtime 使用不同验收契约
QA Contract 有独立审批生命周期
```

当前明确不拆。

---

# 16. REVISE_PLAN 执行流程

## 16.1 支持入口

最终支持：

```text
PLAN_CONFIRM
ART_CONFIRM
QA_RECOVERY
```

Capability Precheck 在用户首次确认前可以触发 Plan Agent 自动自修复，不一定产生 HITL。

---

## 16.2 PLAN_CONFIRM

允许：

```text
APPROVE_PLAN
REVISE_PLAN
CANCEL_RUN
```

---

## 16.3 ART_CONFIRM

允许：

```text
SELECT_ART_A
SELECT_ART_B
REVISE_ART
REVISE_PLAN
CANCEL_RUN
```

例如用户看到美术后发现：

> 其实我不要十个角色，只需要三个。

这是 Plan Scope 问题。

不要求用户取消整个 Run。

---

## 16.4 QA_RECOVERY

根据 RecoveryPolicy 动态产生，例如：

```text
RETRY_IMPLEMENTATION
REVISE_PLAN
CANCEL_RUN
```

或者：

```text
REVISE_PLAN
CANCEL_RUN
```

---

## 16.5 REVISE_PLAN 输入

```text
Current PlanRevision
+
User Feedback
+
FailureReport（如果有）
+
CapabilityProfile
+
Remaining Budget
```

禁止直接把整个 checkpoint 无选择注入模型。

---

## 16.6 结构化输出

```json
{
  "revision_reason": "CAPABILITY_MISMATCH",

  "changes": [
    {
      "requirement_id": "REQ-12",
      "action": "REPLACE",
      "from": "3D open world",
      "to": "2D top-down bounded world",
      "reason": "runtime capability mismatch"
    }
  ],

  "retained_requirements": [],
  "removed_requirements": [],
  "replaced_requirements": [],

  "required_capabilities": {},

  "acceptance_contract": [],

  "design_doc": {}
}
```

---

## 16.7 Validation Pipeline

```text
LLM Output
 ↓
JSON Schema Validation
 ↓
Design Consistency Validation
 ↓
Capability Validation
 ↓
Acceptance Contract Validation
 ↓
Budget Validation
```

非法输出不能写入 Active Plan。

---

## 16.8 新 Plan 必须再次 HITL

Replan 产生：

```text
P2
```

之后必须：

```text
PLAN_CONFIRM
```

禁止：

```text
Failure
 ↓
LLM Replan
 ↓
直接 Code
```

因为 P2 已经改变用户产品定义。

---

# 17. 消息可靠性与 Command 幂等

## 17.1 复用现有 task_outbox

不增加新的：

```text
outbox_events
```

所有 Resume Command 仍使用：

```text
task_outbox
```

完成可靠发布。

---

## 17.2 新增 run_commands

建议：

```text
id
run_id
command_type
payload

source
decision_id nullable

idempotency_key

status

created_at
started_at
completed_at
failed_at
```

Status：

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLED
```

---

## 17.3 Resume Transaction

统一：

```text
BEGIN

Validate expected control_revision

Normalize legacy decision → RunCommand

Insert RunCommand

Write/update resume_grant

Insert task_outbox

Increment control_revision

COMMIT
```

注意：

> 当前 `resume_grant + task_outbox` 原子性已经存在。

本阶段真实增量是：

```text
RunCommand insert
+
control_revision CAS
```

加入同一事务。

---

## 17.4 Worker 幂等

收到：

```text
command_id = CMD123
```

执行前检查：

```text
CMD123.status
```

如果：

```text
SUCCEEDED
```

则：

```text
ACK
return
```

如果：

```text
RUNNING
```

需要结合现有 execution lease 判断：

```text
仍有有效 owner → 不重复执行
lease 已失效 → 接管恢复
```

---

## 17.5 Worker Crash 场景

```text
Command 执行业务写入成功
 ↓
DB COMMIT
 ↓
Worker 在 RabbitMQ ACK 前 Crash
 ↓
RabbitMQ Redelivery
```

第二次消费：

```text
发现 Command 已 SUCCEEDED
 ↓
ACK
```

不能再次生成：

```text
Plan P3
```

---

# 18. Cancel / Pause / Resume 收敛

## 18.1 CANCEL_RUN 只有一个业务语义

当前已有：

```text
/cancel
```

以及 Redis `_check_ctrl` 控制位。

引入：

```text
CANCEL_RUN
```

后不能同时存在两套取消语义。

---

## 18.2 对外 Endpoint 可以保留

保留现有：

```text
POST /cancel
```

作为 Public API。

但内部统一转换为：

```text
RunCommandType.CANCEL_RUN
```

---

## 18.3 PostgreSQL 是取消 SoT

Cancel 请求事务内：

```text
insert CANCEL_RUN command
set durable cancel_requested state
increment control_revision
invalidate current HITL if needed
```

事务成功后再 best-effort：

```text
set Redis cancel control bit
```

---

## 18.4 Redis 只是快速中断通道

Redis `_check_ctrl` 的定位调整为：

> Low-latency Interrupt Signal

而不是：

> Cancellation Source of Truth

即使：

```text
DB commit success
Redis write failure
```

系统仍然知道该 Run 已请求 Cancel。

Worker 在安全点除检查 Redis 外，也必须能够通过持久化状态最终观察到 Cancel。

---

## 18.5 Pause

`/pause` 本期不强制改造成 Workflow Recovery Command。

Pause 属于执行控制，不属于产品语义恢复。

但它同样必须影响：

```text
control_revision
```

避免旧 HITL 决策在控制状态变化后继续提交。

---

# 19. Workflow Versioning

Run 创建时冻结：

```text
workflow_version
```

例如：

```json
{
  "workflow_version": 13
}
```

---

## 19.1 为什么需要

滚动发布期间：

```text
API = New
Worker A = Old
Worker B = New
```

新 API 可能产生：

```text
REVISE_PLAN
```

旧 Worker 不允许：

```text
“不认识但继续按旧逻辑猜”
```

---

## 19.2 Worker Capability

Worker 明确声明：

```text
supported_workflow_versions
```

收到不支持版本：

```text
不得执行
```

进入：

```text
compatibility routing
或 fail-safe retry
```

---

## 19.3 版本概念分离

必须区分：

```text
workflow_version
checkpoint_schema_version
artifact_schema_version
fingerprint_version
```

四者语义不同。

---

# 20. Prompt 与失败证据安全

以下全部视为不可信输入：

```text
generated source code
browser console
DOM text
dependency error
asset metadata
playtest output
external page content
LLM diagnosis
```

进入 Replan Agent 前：

```text
truncate
 ↓
secret redaction
 ↓
normalization
 ↓
structured extraction
 ↓
explicit untrusted delimiter
```

禁止：

```python
prompt += raw_logs
```

---

# 21. Budget 与成本控制

必须显式区分两个完全不同的概念。

## 21.1 现有 PLAN_MAX_ATTEMPTS

当前：

```text
PLAN_MAX_ATTEMPTS = 3
```

含义是：

> 单次 Plan 生成过程中的 Schema / Validator Repair Attempts。

它不是用户跨阶段回炉次数。

为避免误用，文档统一称：

```text
PLAN_GENERATION_REPAIR_MAX_ATTEMPTS
```

代码是否立即 rename 可以单独处理。

---

## 21.2 新增 REPLAN_MAX_REVISIONS

跨阶段策划修订预算使用：

```text
REPLAN_MAX_REVISIONS
```

例如：

```text
2
```

含义：

> 一个 Run 因后置失败产生的新 PlanRevision 次数上限。

---

## 21.3 其他预算

建议：

```text
IMPLEMENTATION_RETRY_MAX_ATTEMPTS
INFRA_RETRY_MAX_ATTEMPTS
REPLAN_MAX_REVISIONS

RUN_TOKEN_BUDGET
RUN_SANDBOX_BUDGET
RUN_COST_BUDGET
```

分别独立。

---

# 22. API / WebSocket / Frontend Contract

本方案不仅是 Backend 改造。

必须包含 Contract Migration。

---

## 22.1 HITL API

可继续兼容旧 Resolve Endpoint，也可以演进为：

```text
POST /runs/{run_id}/hitl/{decision_id}/resolve
```

请求：

```json
{
  "expected_control_revision": 42,
  "command": "revise_plan",
  "feedback": "..."
}
```

---

## 22.2 HITL_WAIT WebSocket Payload

增加：

```json
{
  "decision_id": "...",
  "control_revision": 42,

  "allowed_commands": [
    "retry_implementation",
    "revise_plan",
    "cancel_run"
  ],

  "failure": {
    "failure_class": "CAPABILITY_MISMATCH",
    "summary": "...",
    "suggested_recovery": "REVISE_PLAN"
  }
}
```

---

## 22.3 OpenAPI / Contracts 同步

Phase 2 必须包含：

```text
backend schema update
 ↓
OpenAPI regenerate
 ↓
contracts sync
 ↓
frontend types update
 ↓
HITL UI update
```

不能只改 Python Enum。

---

## 22.4 Frontend Legacy Compatibility

灰度期间前端必须能处理：

```text
legacy decision payload
```

与：

```text
command-based payload
```

直到旧 Workflow Version 基本退出。

---

# 23. 可观测性与审计

关键 Log Context：

```text
run_id
command_id
workflow_version

control_revision

plan_revision_id
art_revision_id
candidate_revision_id

failure_report_id
failure_class

execution_id
```

---

## 23.1 Metrics

建议：

```text
forge_replan_total
forge_replan_success_total
forge_replan_per_run

forge_failure_class_total
forge_failure_class_unknown_total
forge_failure_class_user_corrected_total

forge_code_retry_total
forge_infra_retry_total

forge_command_redelivery_total
forge_command_idempotent_skip_total

forge_stale_decision_total

forge_artifact_stale_total
forge_promotion_rejected_total

forge_replan_incremental_cost
forge_run_completion_after_replan
```

---

## 23.2 Audit Events

建议最少：

```text
PLAN_CREATED
PLAN_REVISED
PLAN_APPROVED

ART_CREATED
ART_SELECTED
ART_STALE

CANDIDATE_CREATED
CANDIDATE_STALE

FAILURE_REPORTED

COMMAND_CREATED
COMMAND_STARTED
COMMAND_COMPLETED

HITL_OPENED
HITL_RESOLVED

PROMOTION_REJECTED
RUN_COMPLETED
RUN_CANCELLED
```

本期不是 Event Sourcing。

这些 Event 用于：

```text
debug
audit
analytics
```

---

# 24. 数据模型

## 24.1 复用

现有：

```text
runs
run checkpoint storage
task_outbox
```

继续使用。

---

## 24.2 新增 / 演进

建议：

```text
runs
  + control_revision
  + workflow_version

run_commands

failure_reports

artifact_revisions
```

如果当前 Artifact 已经有独立表，也可以演进现有结构，而不是一定新建统一大表。

---

## 24.3 不新增

本方案明确不新增：

```text
outbox_events
qa_contract_revisions
```

前者复用：

```text
task_outbox
```

后者并入：

```text
PlanRevision.acceptance_contract
```

---

## 24.4 Checkpoint 定位

Checkpoint 只回答：

> Workflow 当前执行到哪里。

例如：

```json
{
  "phase": "plan_confirm",

  "active_plan_revision_id": "plan_4",
  "active_art_revision_id": null,
  "active_candidate_revision_id": null
}
```

领域历史由：

```text
RunCommand
FailureReport
ArtifactRevision
Audit Event
```

承担。

---

# 25. 分阶段实施计划

由于现有 Transactional Outbox 已完成，原“先建设 Outbox 再做 Replan”的排期取消。

新的关键路径明显缩短。

---

## Phase 0 — Command & Control Foundation

目标：

> 不改变用户行为，先统一恢复语义和并发控制。

实现：

* [ ] 新增 `RunCommandType`
* [ ] 新增 `run_commands`
* [ ] 新增 `runs.control_revision`
* [ ] 新增 `runs.workflow_version`
* [ ] Resume Transaction 写入 `RunCommand`
* [ ] 复用现有 `task_outbox`
* [ ] Worker 增加 `command_id` 幂等检查
* [ ] legacy decision → command adapter
* [ ] adapter 覆盖 `resolve_hitl`
* [ ] adapter 覆盖 `resume_run_control`
* [ ] adapter 覆盖 `retry_run`
* [ ] adapter 覆盖 `dev_requeue`
* [ ] 补齐 `sandbox_failed` legacy mapping

这一阶段不要求 UI 出现 Replan。

---

## Phase 1 — FailureReport Lite & Classification

目标：

> 为 Replan 提供稳定失败证据。

实现：

* [ ] `FailureReport`
* [ ] FailureReport 在 HITL 前冻结
* [ ] FailureReport 创建点：`code_qa_loop_node` exhausted 分支与 `_pause_recoverable`，均先落库再调 `_pause_hitl` / 发暂停事件
* [ ] FailureClass Enum
* [ ] deterministic infra classification
* [ ] implementation classification
* [ ] UNKNOWN fallback
* [ ] classification provenance
* [ ] sanitized failure summary

本阶段不必一次实现全部高级 LLM Diagnosis。

只要能够安全地区分：

```text
infra
implementation
semantic/unknown
```

就足够支撑 Phase 2。

---

## Phase 2 — REVISE_PLAN End-to-End

这是第一个直接产生用户价值的阶段。

实现：

* [ ] QA Recovery 支持 `REVISE_PLAN`
* [ ] `ART_CONFIRM` 支持 `REVISE_PLAN`
* [ ] Replan 使用 FailureReport
* [ ] Replan 结构化输出
* [ ] 新 Plan 必须重新 `PLAN_CONFIRM`
* [ ] `REPLAN_MAX_REVISIONS`
* [ ] HITL API Command Contract
* [ ] `HITL_WAIT` WS Payload 更新
* [ ] OpenAPI regenerate
* [ ] contracts sync
* [ ] Frontend HITL Card 更新
* [ ] stale decision 409 UX
* [ ] **Phase 3 之前的历史保全**：Replan 提交时将旧 design_doc / art_direction 快照写入 checkpoint（如 `superseded` 字段），或确认 forge_messages 已有的 design 消息链足以追溯——Lineage 上线前灰度流量产生的 Replan 历史不能不可见
* [ ] `PLAN_CONFIRM` / `ART_CONFIRM` 新增 `CANCEL_RUN` 的前端按钮与文案（legacy 词表原本没有 cancel，属于行为扩展）

到这里即可正式灰度上线核心“失败后修改策划”。

> **Phase 2 的一致性边界：** 本阶段系统仍是「design_doc 单值覆盖」模型，
> 没有 STALE 标记与旧 Candidate 保留。灰度期间的 Replan run 即按此语义执行，
> 不做复杂复用；Phase 3 上线后新 run 才进入完整 Lineage 模型。
> 上述历史保全 checklist 是这段窗口期的最低要求。

---

## Phase 3 — Immutable Artifact Lineage

目标：

> 防止 Replan 后旧产物污染新流程。

实现：

* [ ] PlanRevision ID
* [ ] ArtRevision ID
* [ ] CandidateRevision ID
* [ ] lineage dependencies
* [ ] `ACTIVE / STALE`
* [ ] old Candidate 保留
* [ ] active candidate pointer 清空
* [ ] Promotion Guard

这一阶段完成后，Replan 达到完整生产一致性模型。

---

## Phase 4 — Capability Precheck

目标：

> 尽量不要让明显无法实现的 Plan 进入 Code。

实现：

* [ ] Design Doc schema 增加 `required_capabilities`
* [ ] Runtime `CapabilityProfile`
* [ ] CapabilityValidator
* [ ] Developability Precheck
* [ ] `CAPABILITY_MISMATCH`
* [ ] 删除关键词式 Capability Blacklist

---

## Phase 5 — Failure Classification Enhancement

目标：

> 提升 Implementation / Acceptance / Capability 的诊断质量。

实现：

* [ ] LLM-assisted ambiguous diagnosis
* [ ] system-generated classification confidence
* [ ] classification correction metrics
* [ ] better RecoveryPolicy recommendations

---

## Phase 6 — Art Dependency Fingerprint

目标：

> 优化 Replan 成本。

实现：

* [ ] Art dependency projection
* [ ] Unicode NFC
* [ ] canonical JSON specification
* [ ] fingerprint version
* [ ] safe Art reuse
* [ ] reuse metrics

该阶段不阻塞核心 Replan。

---

# 26. 测试与验收

DoD 按 Phase 标注。

---

## 26.1 Phase 0

* [ ] `[P0]` 同一个 `command_id` 重复消费只产生一次业务效果
* [ ] `[P0]` DB Commit 后 HTTP Timeout，客户端重试不会重复创建业务结果
* [ ] `[P0]` Worker DB Commit 后、RabbitMQ ACK 前 Crash 可安全 Redeliver
* [ ] `[P0]` 两浏览器同时 Resolve，仅一个成功
* [ ] `[P0]` 旧 HITL 页面 Resolve 返回 `409 STALE_DECISION`
* [ ] `[P0]` 四个 Resume 入口全部经过 Command Normalization
* [ ] `[P0]` `sandbox_failed` legacy 行为不因迁移意外改变
* [ ] `[P0]` 现有 task_outbox 行为保持不变

---

## 26.2 Phase 1

* [ ] `[P1]` HITL 打开之前 FailureReport 已持久化
* [ ] `[P1]` 后续 checkpoint 更新不会改变旧 FailureReport
* [ ] `[P1]` 503 类基础设施错误不会误分类成 Capability Mismatch
* [ ] `[P1]` 证据不足时输出 UNKNOWN
* [ ] `[P1]` 原始日志经过 truncate / redact

---

## 26.3 Phase 2

* [ ] `[P2]` QA Exhausted 后用户能选择 `REVISE_PLAN`
* [ ] `[P2]` Art Confirm 能选择 `REVISE_PLAN`
* [ ] `[P2]` 新 Plan 重新进入 `PLAN_CONFIRM`
* [ ] `[P2]` Replan 输入包含 FailureReport
* [ ] `[P2]` Replan Budget 独立于 `PLAN_MAX_ATTEMPTS`
* [ ] `[P2]` WS Contract 与前端 Types 已同步
* [ ] `[P2]` 旧 Workflow Version 的 HITL UI 仍能操作
* [ ] `[P2]` Replan 后旧 design_doc / art_direction 可追溯（checkpoint 快照或 forge_messages 消息链）
* [ ] `[P2]` `PLAN_CONFIRM` / `ART_CONFIRM` 的 `CANCEL_RUN` 按钮可用且文案准确

---

## 26.4 Phase 3

* [ ] `[P3]` Replan 不删除旧 Plan
* [ ] `[P3]` Replan 不删除旧 Candidate
* [ ] `[P3]` 不兼容 Candidate 标记 STALE
* [ ] `[P3]` STALE Candidate 无法 Promote
* [ ] `[P3]` active Plan 与 Candidate dependency 不一致时 Promotion Guard 拒绝

---

## 26.5 Phase 4

* [ ] `[P4]` unsupported runtime capability 在 Plan Confirm 前可检测
* [ ] `[P4]` “不要使用 3D”不会因为包含字符串 `3D` 被误判
* [ ] `[P4]` RequiredCapabilities 与 CapabilityProfile 产生可解释冲突信息

---

## 26.6 Phase 6

* [ ] `[P6]` Unicode 等价文本 NFC 后产生相同 Fingerprint
* [ ] `[P6]` JSON key 顺序不同不改变 Fingerprint
* [ ] `[P6]` 语义有序数组顺序变化会改变 Fingerprint
* [ ] `[P6]` 不同 fingerprint version 不允许直接复用 Art

---

# 27. Rollout 与回滚

## 27.1 Rollout Gate

Replan UI 增加发布门控：

```text
replan_recovery_enabled
```

推荐：

```text
Internal
 ↓
5% new runs
 ↓
25%
 ↓
100%
```

---

## 27.2 Run 冻结 Workflow Version

新 Run：

```text
workflow_version = N
```

长期暂停 Run 不自动升级到 N+1。

---

## 27.3 回滚

出现问题时：

```text
1. 关闭新 Run 的 REVISE_PLAN UI exposure
2. 停止分配新的 workflow_version
3. 已存在 N 版本 Run 继续由兼容 Worker 处理
4. 保留 DB schema，禁止 destructive rollback
```

不能：

```text
让旧 Worker 用旧语义执行新 Command
```

---

# 28. Non-Goals

## 28.1 不重建 Transactional Outbox

现有：

```text
task_outbox
```

继续使用。

---

## 28.2 不迁移 LangGraph Native Interrupt / Persistence

当前：

```text
PG checkpoint
RabbitMQ
resume grant
execution lock
external HITL
```

保持。

未来维护成本达到阈值后单独 ADR。

---

## 28.3 不做 Fully Connected Graph

跨阶段恢复仍然使用：

```text
Command
 ↓
route_start
```

模式。

---

## 28.4 不做 QA Contract 独立 Revision

Acceptance Contract 属于 PlanRevision。

---

## 28.5 不做 Plan Branch / Merge

只支持：

```text
P1 → P2 → P3
```

不支持：

```text
P2A
P2B
merge
```

---

## 28.6 不做 Art Partial Regeneration

Art：

```text
reuse whole compatible revision
```

或者：

```text
generate new revision
```

本期不 Patch 部分资产。

---

## 28.7 不做 Cross-Run Artifact Sharing

Lineage 只在当前 Run 内成立。

---

## 28.8 不做无确认的自动语义降级

系统可以：

```text
diagnose
suggest
generate revised draft
```

但改变用户产品定义必须 HITL。

---

# 29. 最终架构不变量

## Command

```text
一个 command_id 最多产生一次业务效果。
```

## HITL

```text
一个 control_revision 对应的用户决策只能成功 Resolve 一次。
```

## Failure

```text
触发 HITL 的 FailureReport 必须在 HITL 打开前冻结。
```

## Plan

```text
PlanRevision 不可原地修改。
```

## Artifact

```text
历史 Artifact 不因新版本产生而删除。
```

## Lineage

```text
每个 Art / Candidate 必须能回答自己依赖哪一版 Plan。
```

## Candidate

```text
旧 Candidate 可以存在，但 STALE Candidate 永远不能 Promote。
```

## Infra Recovery

```text
基础设施恢复不能擅自改变用户产品语义。
```

## Semantic Recovery

```text
改变用户产品语义必须经过 HITL。
```

## Messaging

```text
task_outbox 保证任务不丢；
RunCommand 幂等保证重复消息不产生重复业务效果。
```

## Control Revision

```text
Checkpoint Revision 与 HITL Control Revision 是两个独立概念。
```

## Cancellation

```text
PostgreSQL 持久状态是 Cancel SoT；
Redis Control Bit 只负责低延迟中断。
```

## Versioning

```text
Worker 不允许解释自己不支持的 workflow_version。
```

---

# 30. 最终决策

本次工作不再定义为：

> “QA Failed 页面增加一个回炉策划按钮。”

正式定义为：

> **GameForge Cross-stage Replan & Recovery + Artifact Lineage 建设。**

现有系统已经具备：

```text
PostgreSQL Transaction
Task Outbox
RabbitMQ Reliable Dispatch
Resume Grant
Execution Lock
Lease Recovery
```

因此不重建消息基础设施。

本次真正需要补齐的是：

```text
1. RunCommand
2. control_revision
3. command-level idempotency
4. FailureReport
5. Failure Classification
6. REVISE_PLAN Recovery
7. Immutable Artifact Revision
8. Artifact Lineage
9. Promotion Guard
10. Workflow Version
11. Capability Validation
```

实施顺序确定为：

```text
Phase 0
Command / control_revision / idempotency

        ↓

Phase 1
FailureReport Lite / conservative classification

        ↓

Phase 2
REVISE_PLAN end-to-end
Frontend Contract
正式产生用户价值

        ↓

Phase 3
Immutable Artifact Lineage
Promotion Guard

        ↓

Phase 4
Capability Precheck

        ↓

Phase 5
Classification Enhancement

        ↓

Phase 6
Art Fingerprint / Reuse Optimization
```

其中：

> **Phase 0 + Phase 1 完成后即可开始交付 REVISE_PLAN，不需要等待重新建设 Outbox，也不需要等待完整 Artifact Lineage 或 Capability System 全部完成。**

但在 Phase 3 完成之前：

> Replan 后的旧 Art / Candidate 采用保守失效策略，不做复杂复用。

最终原则：

> **失败不是回到旧状态，而是产生下一版设计的证据。**

> **状态可以前进，历史不能被抹掉。**

> **Phase 描述“现在在哪里”，Command 描述“下一步要做什么”，FailureReport 描述“为什么这么做”。**

> **消息可以重复，业务结果不能重复。**

> **基础设施失败由系统自动恢复，产品语义变化由用户决定。**

> **先保证正确性和可恢复性，再优化 Artifact 复用与生成成本。**
