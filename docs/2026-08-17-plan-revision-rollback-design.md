# 策划稿跨阶段修订与失败恢复（Replan & Recovery）生产级技术方案

* **Status:** Proposed（待评审）
* **Date:** 2026-08-17
* **Owners:** TBD
* **Related:**

  * `backend/app/forge/graph.py`：主图 / `route_start` / HITL 路由
  * `backend/app/forge/hitl.py`：HITL 决策与合法命令
  * `backend/app/forge/subgraphs/code_qa_loop.py`：CodeQaLoop 子图
  * `backend/app/forge/state.py`：Run checkpoint / state persistence
  * `backend/app/forge/queue.py`：RabbitMQ enqueue / resume
  * `docs/adr/ADR-10-checkpoint-hitl-idempotency.md`
* **拟新增 / 修订 ADR：**

  * ADR-10：补充 HITL resume 不再假设单一恢复目标
  * 新增 ADR：`Workflow Versioning & Artifact Lineage`
  * 新增 ADR：`Run Command / Decision Request / Outbox Reliability`

---

## 0. 执行摘要

GameForge 当前工作流已经具备完整的策划、美术、开发、自动 QA 与 HITL 暂停恢复能力，但整个系统仍隐含一个单向假设：

> 上游策划一旦确认，后续阶段只能继续向前；如果开发阶段发现策划本身不可实现，只能继续修代码或放弃整个 run。

这一假设在真实生产环境下不成立。

开发和 QA 不只是“验证代码是否正确”，同时也是对策划可实现性的后置验证。某些需求只有进入真实构建、浏览器执行、性能测试或试玩阶段后，才能确认其超出当前运行时能力、预算或验收能力。

因此，本方案不再把问题定义成简单的 **Plan Rollback**，而是建立一套正式的：

> **Cross-stage Replan & Recovery Model**

核心原则是：

**历史永远向前，不做破坏性回滚。**

发生 QA 或能力失败后，不修改或删除旧策划，而是创建新的 `PlanRevision`；旧的 Art、Candidate 等产物继续保留，但根据依赖关系被标记为 `STALE` / `SUPERSEDED`，不得继续 Promote。

本方案保留现有：

* FastAPI
* LangGraph
* PostgreSQL checkpoint
* Redis cache
* RabbitMQ
* 云沙箱
* WebSocket
* 外部 HITL 暂停 / 恢复

等核心技术选型，不重写工作流框架。

本次架构升级的核心不是“给 `qa_failed` 多加一个按钮”，而是正式建立 GameForge 的 Workflow Domain Model：

1. `RunCommand`
2. `DecisionRequest`
3. `FailureReport`
4. Immutable Artifact Revision
5. Artifact Dependency / Lineage
6. Workflow Versioning
7. Capability Validation
8. Reliable Command Delivery
9. Promotion Invariants
10. Failure Recovery Policy

---

# 1. 项目背景

GameForge 是一个 AI 辅助浏览器游戏创作平台。

用户通过自然语言描述玩法创意，系统自动完成：

1. AI 策划
2. 用户确认策划
3. 美术方案生成
4. 用户确认美术
5. 游戏代码生成
6. 云沙箱构建
7. 浏览器自动试玩
8. 自动 QA / 修复
9. 最终版本交付、下载与发布

主要技术栈：

```text
FastAPI
    │
    ▼
LangGraph Workflow
    │
    ├── Plan
    ├── Art
    ├── Code
    └── QA
    │
    ▼
PostgreSQL RunCheckpoint
Redis Cache
RabbitMQ
Cloud Sandbox
Playwright
WebSocket
```

当前系统采用：

> **单步执行器 + 外部暂停恢复 + 集中式路由**

模式。

主图中的节点执行完成后，如果需要 HITL：

```text
Node
 ↓
_pause_hitl()
 ↓
Run = PAUSED
 ↓
Graph END
 ↓
User resolves decision
 ↓
Resume job enqueue
 ↓
Worker starts again
 ↓
route_start()
 ↓
Next node
```

因此本方案不需要把 LangGraph 改造成 Fully Connected Graph，也不需要通过图内边实现复杂回环。

---

# 2. 问题定义

## 2.1 当前用户问题

标准生成链路：

```text
Plan
 ↓
Plan Confirm
 ↓
Art
 ↓
Art Confirm
 ↓
Code + QA
 ↓
Done
```

CodeQaLoop 当前能够处理：

* build error
* runtime error
* Playwright failure
* quality failure
* implementation repair
* infra replay

但当达到最大修复次数后：

```text
attempt >= max_attempts
 ↓
qa_failed
 ↓
HITL
```

用户当前只能：

```text
approve
modify
```

两者最终仍回：

```text
code_qa_loop
```

于是存在三个生产级缺口。

---

## 2.2 缺口一：开发失败无法修改上游策划

例如用户要求：

> 制作一个 3D 开放世界多人联机生存游戏。

策划阶段可能生成了一个逻辑合理但当前 GameForge Runtime 无法实现的 Design Doc。

用户确认策划后：

```text
Plan
 ↓
Art
 ↓
Code Attempt 1
 ↓
Fail
 ↓
Code Attempt 2
 ↓
Fail
 ↓
Code Attempt 3
 ↓
Fail
```

此时继续修 Code 没有意义。

真正合理的恢复动作可能是：

```text
3D → 2D
开放世界 → 小型地图
多人同步 → 单人玩法
复杂物理 → 简化碰撞规则
20 分钟 Session → 5 分钟 Session
```

当前系统没有这条路径。

---

## 2.3 缺口二：失败证据没有形成稳定的数据资产

当前 `revise_plan` 主要依赖：

```text
原 design_doc
+
用户 modify_text
```

但是 QA 已经产生了大量高价值证据：

```text
build errors
runtime errors
playtest failures
qa diagnosis
failure kind
attempt history
resource usage
```

如果这些信息没有冻结成稳定结构，而是在 `revise_plan` 执行时临时从当前 checkpoint 中读取，会出现：

* failure context 被后续 attempt 覆盖
* 恢复时读到不同版本的数据
* 无法审计“当时为什么建议用户修改策划”
* 无法稳定复现
* prompt 输入与 UI 展示信息不一致

---

## 2.4 缺口三：产物缺乏正式血缘关系

当前逻辑上存在：

```text
Design Doc
 ↓
Art Direction
 ↓
Candidate
```

但系统无法稳定回答：

> Candidate C7 是基于哪一版策划生成？

> Art A3 是否仍然兼容新的 Plan P4？

> Plan 修改后是否需要重新生成美术？

> 某个旧 Candidate 为什么不能 Promote？

缺乏正式 Artifact Lineage 后，系统只能：

* 全量重新生成，浪费成本；
* 或复用旧产物，产生一致性风险。

---

## 2.5 缺口四：失败类型与恢复策略耦合在 phase 上

当前存在类似：

```text
sandbox_failed
qa_failed
```

这样的 phase。

但：

```text
sandbox_failed
```

可能代表：

* 云 Sandbox 服务临时不可用；
* Build Timeout；
* 内存不足；
* 用户策划要求的能力不支持；
* 代码实现 bug；
* 第三方资源失败。

这些失败的正确恢复行为完全不同。

因此生产系统不应该使用：

```text
phase → recovery action
```

作为核心模型。

应改为：

```text
FailureClass
 ↓
RecoveryPolicy
 ↓
AllowedCommands
```

---

# 3. 根因分析

本问题不是 LangGraph 缺乏回环能力。

真正根因有六个。

## 3.1 HITL decision 使用上下文依赖型弱语义词汇

当前：

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

实际上表达的是：

> 再进行一次实现尝试。

而：

```text
qa_failed + modify
```

表达的是：

> 带用户反馈重新尝试实现。

离开 `phase` 后，`approve` / `modify` 本身没有业务含义。

随着工作流增长，会最终演变为：

```python
if phase == ...
    if decision == ...
        ...
```

形成隐式状态机。

---

## 3.2 Failure Evidence 没有不可变快照

Failure 是工作流状态的一部分，而不是独立领域对象。

这导致恢复动作与“当前 checkpoint”过度耦合。

---

## 3.3 Artifact 是值，不是 Revision

当前系统更接近：

```text
design_doc = {...}
art_direction = {...}
candidate = {...}
```

生产级模型应该是：

```text
PlanRevision P1
PlanRevision P2

ArtRevision A1

CandidateRevision C1
CandidateRevision C2
```

每个版本不可变。

---

## 3.4 没有正式依赖关系

系统缺少：

```text
A1 depends_on P1
C1 depends_on P1 + A1
```

因此无法可靠执行 invalidation。

---

## 3.5 可开发性检查发生得太晚

明显的 capability mismatch 应尽可能在：

```text
Plan
 ↓
Capability Validation
 ↓
Plan Confirm
```

期间发现，而不是消耗三次代码生成后才发现。

---

## 3.6 消息投递与数据库状态缺乏统一可靠性模型

HITL Resolve 涉及：

```text
DB update
+
RabbitMQ publish
```

如果缺少 Transactional Outbox，会出现经典不一致：

### Case A

```text
DB commit success
RabbitMQ publish failed
```

Run 看似已恢复，但永远没有 Worker 继续执行。

### Case B

```text
RabbitMQ publish success
HTTP response timeout
```

用户重试 Resolve，产生重复命令。

因此生产模型必须接受：

> 消息可能重复投递。

系统目标不是“Exactly Once Delivery”，而是：

> **At-Least-Once Delivery + Exactly-Once Effect**

---

# 4. 目标架构

整体业务模型：

```text
                         CapabilityProfile
                                │
                                ▼
User Idea ────────→ Plan Revision P1
                         │
                         ├── Capability Validate
                         │
                         ▼
                   QA Contract Q1
                         │
                         ▼
                    Plan Confirm
                         │
                         ▼
                  Art Revision A1
                         │
                         ▼
                    Art Confirm
                         │
                         ▼
                Candidate Revision C1
                         │
                         ▼
                    Code / QA
                         │
              ┌──────────┴────────────┐
              │                       │
             PASS                    FAIL
              │                       │
              ▼                       ▼
       Promotion Guard          FailureReport F1
              │                       │
              ▼            ┌──────────┼──────────────┐
            DONE            │          │              │
                         Infra       Impl.        Capability
                       Transient     Defect       Mismatch
                           │           │              │
                           ▼           ▼              ▼
                       Auto Retry   Code Retry   DecisionRequest
                                                      │
                                                 REVISE_PLAN
                                                      │
                                                      ▼
                                               Plan Revision P2
                                                      │
                                              Dependency Check
                                                ┌─────┴─────┐
                                                │           │
                                             reuse A1   generate A2
                                                │           │
                                                └─────┬─────┘
                                                      ▼
                                               Candidate C2
```

底层可靠执行模型：

```text
Client
  │
  ▼
FastAPI
  │
  ▼
PostgreSQL Transaction
 ├── Resolve DecisionRequest
 ├── Insert RunCommand
 ├── CAS Run Revision
 └── Insert Outbox Event
  │
 COMMIT
  │
  ▼
Outbox Publisher
  │
  ▼
RabbitMQ
  │
  ▼
Worker
  │
  ▼
Idempotent Command Execution
```

---

# 5. 核心设计原则

## 5.1 历史只追加，不做破坏性回滚

所谓 `revise_plan` 实际不是 rollback。

禁止：

```text
P1 → overwrite → P2
```

应使用：

```text
P1
 ↓ superseded_by
P2
```

任何已经产生的：

* Plan
* Art
* Candidate
* Failure Report
* QA Result

默认都不物理删除。

---

## 5.2 旧产物可以失效，但不能消失

Plan P2 创建以后：

```text
active_plan = P2
```

如果旧 Candidate C1 不兼容：

```text
C1.status = STALE
C1.stale_reason = PLAN_SUPERSEDED
```

而不是：

```text
candidate = null
DELETE candidate
```

Run 当前活跃 Candidate 可以置空：

```text
active_candidate_revision_id = NULL
```

但历史 Candidate 必须保留。

---

## 5.3 语义变化必须 HITL，机械恢复自动执行

需要 HITL：

```text
3D → 2D
多人 → 单人
5 关 → 3 关
删除某玩法机制
修改核心验收标准
重新生成美术
```

不需要 HITL：

```text
RabbitMQ redelivery
Sandbox 503
短暂网络故障
Browser startup timeout
临时镜像拉取失败
```

原则：

> **改变用户产品意图的操作需要 HITL。恢复基础设施状态的操作应该自动完成。**

---

## 5.4 Workflow 恢复必须幂等

所有外部恢复请求都必须具有稳定：

```text
command_id
```

重复投递：

```text
Command X
Command X
Command X
```

只能产生一次业务效果。

---

## 5.5 在进入昂贵阶段前尽早验证

优先：

```text
Plan
 ↓
Validate
 ↓
Reject / Replan
```

而不是：

```text
Plan
 ↓
Art
 ↓
Code × 3
 ↓
发现 Plan 根本无法实现
```

---

# 6. RunCommand：正式替代上下文型 decision

## 6.1 新命令模型

新增：

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

后续可扩展：

```text
CHANGE_RUNTIME
ACCEPT_DEGRADED_RESULT
RESTART_FROM_ART
```

但本期不实现。

---

## 6.2 不再使用 `approve` 表示 QA Retry

旧语义：

```text
qa_failed + approve
```

新语义：

```text
RETRY_IMPLEMENTATION
```

旧：

```text
qa_failed + modify
```

新：

```text
RETRY_IMPLEMENTATION
feedback = "..."
```

优点：

* API 自解释；
* Event Log 自解释；
* 不依赖 phase 才能理解；
* 降低 `route_start()` 复杂度；
* 未来新增流程不需要继续扩散语义不明的 `approve/modify`。

---

## 6.3 向后兼容

迁移期间 API 可以暂时接受旧 decision：

```text
approve
modify
```

在 API Boundary 转成新命令。

例如：

```python
legacy_map = {
    ("qa_failed", "approve"): RETRY_IMPLEMENTATION,
    ("qa_failed", "modify"): RETRY_IMPLEMENTATION,
    ("plan_confirm", "approve"): APPROVE_PLAN,
    ("plan_confirm", "modify"): REVISE_PLAN,
}
```

内部 Worker 与新数据表只处理正式 `RunCommandType`。

旧 vocabulary 在兼容窗口后删除。

---

# 7. DecisionRequest：正式 HITL 对象

当前 HITL 不应只表现为：

```text
run.phase = qa_failed
```

新增正式领域对象：

```text
DecisionRequest
```

建议字段：

```text
id
run_id
run_revision

request_type
phase_snapshot

failure_report_id nullable

allowed_commands

status:
    OPEN
    RESOLVED
    EXPIRED
    CANCELLED

created_at
resolved_at

resolved_command_id nullable
```

示例：

```json
{
  "id": "dr_123",
  "run_id": "run_456",
  "run_revision": 37,
  "request_type": "QA_RECOVERY",
  "phase_snapshot": "qa_failed",
  "failure_report_id": "failure_789",
  "allowed_commands": [
    "retry_implementation",
    "revise_plan",
    "cancel_run"
  ],
  "status": "OPEN"
}
```

---

# 8. HITL Resolve API

建议请求：

```http
POST /runs/{run_id}/decision-requests/{decision_request_id}/resolve
```

Request：

```json
{
  "command": "revise_plan",
  "feedback": "改为 2D 俯视角，取消多人同步",
  "idempotency_key": "client-generated-key"
}
```

服务端事务必须校验：

```text
DecisionRequest.status == OPEN

DecisionRequest.run_id == Run.id

DecisionRequest.run_revision == Run.revision

command ∈ DecisionRequest.allowed_commands
```

---

## 8.1 CAS 防陈旧请求

Resolve 时：

```sql
UPDATE runs
SET revision = revision + 1
WHERE id = :run_id
  AND revision = :expected_revision;
```

若：

```text
affected_rows != 1
```

返回：

```http
409 Conflict
```

业务错误：

```text
STALE_DECISION
```

这样自然处理：

* 用户双击；
* 两个浏览器 Tab；
* 旧页面操作；
* 请求重试；
* WebSocket 延迟。

---

# 9. FailureReport：冻结失败证据

## 9.1 FailureReport 必须在失败发生时创建

禁止 `revise_plan` 执行时再动态：

```python
checkpoint.load_current_failure()
```

正确流程：

```text
QA Attempt Exhausted
 ↓
Create immutable FailureReport F1
 ↓
Create DecisionRequest referring F1
 ↓
PAUSE
```

---

## 9.2 FailureReport 数据模型

建议：

```json
{
  "id": "failure_123",
  "run_id": "run_1",

  "plan_revision_id": "plan_3",
  "art_revision_id": "art_2",
  "candidate_revision_id": "candidate_8",

  "failure_class": "CAPABILITY_MISMATCH",
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
      "stage": "playtest",
      "error_code": "PLAYTEST_TIMEOUT",
      "summary": "..."
    }
  ],

  "diagnosis": {
    "summary": "...",
    "confidence": 0.87,
    "suggested_recovery": "REVISE_PLAN"
  },

  "resource_usage": {
    "sandbox_seconds": 84,
    "llm_tokens": 12345
  },

  "created_at": "..."
}
```

FailureReport 创建后不可修改。

如需重新诊断，创建：

```text
FailureDiagnosisRevision
```

或新的报告。

P0 可暂不拆 Diagnosis Revision。

---

# 10. Failure Classification

停止使用简单：

```text
product / infra
```

二分类。

建议最少：

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

## 10.1 Recovery Policy

| FailureClass            | 默认动作              | HITL              |
| ----------------------- | ----------------- | ----------------- |
| `INFRA_TRANSIENT`       | 自动 infra retry    | 否                 |
| `IMPLEMENTATION_DEFECT` | CodeQaLoop repair | retry budget 耗尽后是 |
| `CAPABILITY_MISMATCH`   | 推荐 `REVISE_PLAN`  | 是                 |
| `ACCEPTANCE_MISMATCH`   | 推荐 `REVISE_PLAN`  | 是                 |
| `RESOURCE_EXCEEDED`     | 自动降级建议 / 用户选择     | 是                 |
| `POLICY_SECURITY`       | 禁止继续原方案，要求调整      | 是                 |
| `UNKNOWN`               | 默认保守进入人工恢复        | 是                 |

---

## 10.2 `sandbox_failed` 不再等价于需要用户决策

例如：

```text
Sandbox API 503
```

应：

```text
INFRA_TRANSIENT
 ↓
automatic retry
```

而不是：

```text
sandbox_failed
 ↓
让用户选择 revise_plan
```

只有 Sandbox 暴露出的真实原因属于：

```text
CAPABILITY_MISMATCH
RESOURCE_EXCEEDED
POLICY_SECURITY
```

时才进入语义恢复。

---

# 11. Artifact Revision：不可变产物模型

## 11.1 Artifact 类型

正式引入 Artifact Revision 概念。

至少包含：

```text
PLAN
QA_CONTRACT
ART_DIRECTION
CANDIDATE
QA_REPORT
```

每次生成新版本创建新 ID。

---

## 11.2 PlanRevision

示例：

```json
{
  "id": "plan_4",
  "run_id": "run_1",
  "artifact_type": "PLAN",

  "revision": 4,

  "supersedes": "plan_3",

  "payload_uri": "...",
  "payload_hash": "...",

  "created_by_command_id": "cmd_9",

  "created_at": "..."
}
```

禁止直接覆盖 P3。

---

## 11.3 ArtRevision

```json
{
  "id": "art_5",

  "artifact_type": "ART_DIRECTION",

  "dependencies": {
    "plan_revision_id": "plan_4"
  },

  "dependency_fingerprint": "...",

  "status": "ACTIVE"
}
```

---

## 11.4 CandidateRevision

```json
{
  "id": "candidate_12",

  "artifact_type": "CANDIDATE",

  "dependencies": {
    "plan_revision_id": "plan_4",
    "art_revision_id": "art_5",
    "qa_contract_revision_id": "qa_4"
  },

  "status": "ACTIVE"
}
```

---

# 12. Artifact 状态

建议：

```text
ACTIVE
STALE
SUPERSEDED
FAILED
PROMOTED
ARCHIVED
```

---

## 12.1 Replan 后禁止删除旧 Candidate

旧行为计划：

```text
candidate_version = null
```

调整为：

```text
active_candidate_revision_id = null
```

历史 Candidate 保留：

```text
candidate_8.status = STALE
candidate_8.stale_reason = PLAN_SUPERSEDED
```

这样保留：

* Debug 证据；
* 成本审计；
* 用户历史；
* 失败复现；
* 模型评估数据；
* 版本比较能力。

---

# 13. Artifact Dependency 与失效传播

基本依赖：

```text
Plan P1
 │
 ├── QAContract Q1
 │
 └── Art A1
      │
      └── Candidate C1
```

Plan P2 创建以后不能简单认为所有下游一定失效。

需要：

```text
dependency compatibility check
```

---

# 14. Dependency Fingerprint

仅依赖：

```text
plan_rev
```

过于粗粒度。

例如：

```text
P1：敌人血量 = 100
P2：敌人血量 = 120
```

可能不影响 Art。

因此 Art 生成时计算：

```text
art_dependency_fingerprint
```

输入可包括：

```text
visual_style
color_palette
asset_needs
entity_visual_descriptions
ui_structure
environment_visual_requirements
animation_requirements
```

执行：

```text
canonical JSON
 ↓
SHA-256
```

得到：

```text
art_dependency_fingerprint
```

新 Plan P2：

```text
fingerprint(P1) == fingerprint(P2)
```

则 A1 可以继续兼容。

---

## 14.1 默认策略

P0：

> Replan 后默认重新生成 Art。

P1：

> 增加 Dependency Fingerprint，在确定 Art 依赖未变化时允许复用。

这样保证 P0 正确性优先，P1 再优化成本。

---

# 15. Promotion Guard

任何 Candidate Promote 前必须执行最终 invariant。

至少：

```python
candidate.plan_revision_id == run.active_plan_revision_id

candidate.art_revision_id == run.active_art_revision_id

candidate.qa_contract_revision_id == run.active_qa_contract_revision_id

candidate.status == ACTIVE

candidate.qa_status == PASSED
```

并再次确认：

```text
dependency fingerprints compatible
```

任何条件失败：

```text
PROMOTION_REJECTED_STALE_ARTIFACT
```

不能依赖前面路由“应该已经正确”。

Promotion Guard 是最后安全边界。

---

# 16. CapabilityProfile：替代关键词黑名单

删除以下设计：

> technical_constraints / acceptance_criteria 不允许出现“3D”“物理引擎”“网络同步”等关键词。

关键词 lint 无法正确表达真正的平台能力。

例如：

```text
“不要使用 3D”
```

并不要求 3D。

```text
“模拟 3D 视觉效果”
```

也未必需要真正 WebGL 3D。

---

## 16.1 Runtime Capability Profile

平台维护结构化：

```json
{
  "profile_version": "2026-08-17.1",

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

  "persistent_database": false,

  "limits": {
    "max_build_seconds": 120,
    "max_bundle_mb": 30,
    "max_asset_count": 80
  }
}
```

---

## 16.2 Plan RequiredCapabilities

Plan 生成后结构化抽取：

```json
{
  "renderer": "canvas2d",
  "physics": "2d_optional",
  "multiplayer": false,
  "backend": false,
  "estimated_asset_count": 24
}
```

然后执行确定性：

```text
RequiredCapabilities
        ×
CapabilityProfile
        ↓
CapabilityValidator
```

失败：

```text
CAPABILITY_MISMATCH
```

在 Plan Confirm 之前处理。

---

# 17. Developability Precheck

新流程：

```text
PLAN NODE
 ↓
schema validation
 ↓
requirement extraction
 ↓
capability validation
 ↓
budget estimation
 ↓
acceptance criteria validation
 ↓
PLAN_CONFIRM
```

如果明显不可开发：

```text
PLAN
 ↓
PRECHECK FAILED
 ↓
自动要求 Plan Agent 重新约束一次
 ↓
仍失败
 ↓
向用户展示能力冲突
```

避免进入 Art 和 Code 后再失败。

---

# 18. QA Contract

当前：

```text
design_doc.acceptance_criteria
```

已经承担机器验收规格职责。

正式拆出：

```text
QAContractRevision
```

示例：

```json
{
  "id": "qa_7",

  "criteria": [
    {
      "id": "AC-01",
      "description": "玩家可以使用方向键移动",
      "severity": "BLOCKER",
      "testability": "AUTOMATED",
      "strategy": "PLAYWRIGHT",
      "timeout_seconds": 5
    },
    {
      "id": "AC-02",
      "description": "整体视觉风格应具有轻松氛围",
      "severity": "NON_BLOCKER",
      "testability": "LLM_REVIEW"
    }
  ]
}
```

这样能够区分：

```text
Implementation Failure
```

与：

```text
Specification / Acceptance Failure
```

---

# 19. REVISE_PLAN 工作流

## 19.1 触发来源

本期支持：

```text
PLAN_CONFIRM
ART_CONFIRM
QA_RECOVERY
CAPABILITY_PRECHECK
```

其中：

### Plan Confirm

```text
REVISE_PLAN
```

属于正常策划编辑。

### Art Confirm

允许：

```text
SELECT_ART_A
SELECT_ART_B
REVISE_ART
REVISE_PLAN
```

用户如果在看美术时发现上游策划范围不合理，不要求 Cancel 整个 Run。

### QA Recovery

允许：

```text
RETRY_IMPLEMENTATION
REVISE_PLAN
CANCEL_RUN
```

具体 Allowed Commands 由 Recovery Policy 决定。

---

# 20. REVISE_PLAN 输入

模型输入不是直接拼原始 checkpoint。

输入为稳定对象：

```text
Current PlanRevision
+
User Feedback
+
FailureReport（如存在）
+
CapabilityProfile
+
Budget Context
```

例如：

```text
当前策划版本：P3

用户修改意见：
改为 2D 俯视视角，不需要多人同步。

上一轮失败摘要：
FailureClass: CAPABILITY_MISMATCH

Attempt 1:
BUILD_ERROR ...

Attempt 2:
PLAYTEST_TIMEOUT ...

Attempt 3:
RESOURCE_EXCEEDED ...

诊断：
当前策划同时要求 3D 场景、大地图以及实时多人同步，
超出当前运行时能力。

当前平台能力：
- Canvas2D: supported
- Phaser2D: supported
- WebGL 3D: unsupported
- Realtime Multiplayer: unsupported
```

---

# 21. REVISE_PLAN 结构化输出

禁止只让模型输出自然语言“保留项 / 削减项 / 替代项”。

建议 schema：

```json
{
  "revision_reason": "CAPABILITY_MISMATCH",

  "changes": [
    {
      "requirement_id": "REQ-12",
      "action": "REPLACE",
      "from": "3D third-person open world",
      "to": "2D top-down bounded map",
      "reason": "current runtime does not support required 3D stack"
    }
  ],

  "retained_requirements": [],

  "removed_requirements": [],

  "replaced_requirements": [],

  "required_capabilities": {},

  "design_doc": {}
}
```

---

# 22. Plan Revision Validation

模型输出后必须经过 deterministic validation：

```text
JSON Schema
 ↓
Design Doc Validator
 ↓
Capability Validator
 ↓
QA Contract Validator
 ↓
Budget Validator
 ↓
Consistency Validator
```

任何一层失败：

```text
LLM repair
```

达到 validator retry budget 后：

```text
进入人工错误处理
```

而不是把非法 Plan 写进 active state。

---

# 23. Failure Context Prompt Safety

以下内容全部视为 **Untrusted Input**：

* Console Log
* Browser DOM Text
* Generated Code
* Dependency Error
* Playtest Error
* External Asset Content
* Model-generated diagnostics

进入 Replan Prompt 前：

```text
truncate
 ↓
redact secrets
 ↓
normalize
 ↓
structure
 ↓
delimiter wrap
```

禁止：

```python
prompt += raw_console_logs
```

FailureReport 中优先存：

```text
structured error
+
sanitized excerpt
```

而不是无上限保存并注入全部原始日志。

---

# 24. Retry Budget 与成本控制

不采用：

> revise_plan 默认无限，只依赖 run 总 token / 总时长。

生产环境需要分层预算：

```text
run_cost_budget

llm_token_budget

sandbox_runtime_budget

implementation_retry_budget

infra_retry_budget

plan_revision_budget
```

默认值示例：

```text
implementation retry = 3
infra transient retry = 5
replan = 2
```

实际配置化，不硬编码。

---

## 24.1 Retry 行为

### Infra Retry

推荐：

```text
exponential backoff
+
jitter
```

不进入用户 HITL。

### Implementation Retry

CodeQaLoop 内执行，耗尽后生成 FailureReport。

### Replan Budget

达到阈值后：

```text
不再自动建议无限回炉
```

向用户展示：

> 当前 Run 已进行了多次策划调整。继续将产生额外生成和测试成本。

用户显式确认后才允许继续。

---

# 25. RabbitMQ + PostgreSQL 可靠性

## 25.1 Transactional Outbox

HITL Resolve 不直接：

```text
DB commit
then RabbitMQ publish
```

改成一个 PostgreSQL Transaction：

```text
BEGIN

CAS Run Revision

Resolve DecisionRequest

Insert RunCommand

Insert OutboxEvent

COMMIT
```

独立 Publisher：

```text
SELECT pending outbox
 ↓
RabbitMQ publish
 ↓
mark published
```

---

## 25.2 RunCommand

建议：

```text
id
run_id
command_type
payload
decision_request_id
idempotency_key
status
created_at
started_at
completed_at
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

## 25.3 Worker 幂等

Worker 收到：

```text
command_id = CMD123
```

执行前：

```text
检查 CMD123 是否已经 SUCCEEDED
```

如果已执行：

```text
ACK
return
```

如果 Worker：

```text
DB commit success
RabbitMQ ACK 前 crash
```

RabbitMQ redelivery 后不会产生第二次业务效果。

---

# 26. Run Execution Lock

现有 execution lock 保留。

建议锁粒度：

```text
run_id
```

保证同一个 Run 同时只有一个 active workflow mutation。

但锁不是幂等替代品。

生产正确性需要：

```text
Run Lock
+
Run Revision CAS
+
Command Idempotency
```

三者同时存在。

---

# 27. Workflow Versioning

本方案明确要求增加：

```text
workflow_version
```

Run 创建时冻结。

例如：

```json
{
  "run_id": "...",
  "workflow_version": 13
}
```

---

## 27.1 为什么必须版本化

滚动发布过程中可能出现：

```text
API = New Version

Worker A = Old Version
Worker B = New Version
```

如果新 API 产生：

```text
REVISE_PLAN
```

旧 Worker 不认识该命令，则存在生产事故风险。

因此 Worker 执行前验证：

```text
supported_workflow_versions
```

不支持：

```text
NACK / move to compatibility worker / fail-safe
```

禁止默默使用新逻辑解释旧 Run。

---

## 27.2 三类版本分离

至少区分：

```text
workflow_version
checkpoint_schema_version
artifact_schema_version
```

含义：

### workflow_version

业务状态机语义。

### checkpoint_schema_version

Run state 序列化格式。

### artifact_schema_version

Plan / Art / QA Contract 等数据格式。

禁止用一个 `version` 字段同时表达三个概念。

---

# 28. Feature / Rollout Gate

原方案“无需 Feature Flag”调整为：

本功能必须具备最小发布门控。

例如：

```text
replan_recovery_enabled
```

作用不是长期业务逻辑，而是发布安全。

推荐：

```text
Internal
 ↓
5%
 ↓
25%
 ↓
100%
```

发生问题时：

```text
关闭新 DecisionRequest 中的 REVISE_PLAN
```

已有旧 Run 仍按照冻结的：

```text
workflow_version
```

恢复。

---

# 29. LangGraph 使用边界

本期：

> **不迁移 LangGraph 原生 persistence / interrupt。**

原因不是原生能力不足，而是当前系统已经拥有稳定：

```text
PG checkpoint
RabbitMQ
HITL API
resume
execution lock
WebSocket lifecycle
```

迁移会同时影响大量生产语义。

本次只增强现有 Domain Layer。

---

## 29.1 后续重新评估条件

当以下情况持续出现时单独 ADR：

* 自研 checkpoint 恢复 bug 明显增多；
* HITL plumbing 维护成本过高；
* Workflow State migration 复杂；
* 大量逻辑重复 LangGraph durable execution；
* 调试和 replay 成本过高。

原则：

> 同一 Run 只能有一个真正的 Workflow SoT。

禁止长期同时维护两套持久化状态机。

---

# 30. route_start 重构

短期仍保留集中路由。

但避免：

```python
if phase == ...
    if decision == ...
```

不断增长。

推荐：

```python
TRANSITIONS = {
    RunCommandType.APPROVE_PLAN: "art_options",
    RunCommandType.REVISE_PLAN: "revise_plan",
    RunCommandType.REVISE_ART: "revise_art_options",
    RunCommandType.RETRY_IMPLEMENTATION: "code_qa_loop",
}
```

复杂 recovery 使用函数：

```python
next_node = recovery_policy.resolve(
    run=run,
    command=command,
    failure_report=failure_report,
)
```

`route_start()` 只承担：

```text
load active command
validate workflow version
validate command freshness
resolve transition
```

不承担全部业务策略。

---

# 31. 新恢复流

## 31.1 QA Implementation Failure

```text
Code Attempt
 ↓
IMPLEMENTATION_DEFECT
 ↓
attempt < budget
 ↓
automatic Code Repair
```

预算耗尽：

```text
FailureReport
 ↓
DecisionRequest
 ↓
RETRY_IMPLEMENTATION
REVISE_PLAN
CANCEL_RUN
```

---

## 31.2 Capability Mismatch

```text
QA
 ↓
CAPABILITY_MISMATCH
 ↓
FailureReport
 ↓
DecisionRequest
```

默认 UI 强推荐：

```text
REVISE_PLAN
```

仍可根据产品策略允许：

```text
RETRY_IMPLEMENTATION
```

但 UI 应提示成功概率低。

---

## 31.3 Infra Failure

```text
Sandbox 503
 ↓
INFRA_TRANSIENT
 ↓
Retry Policy
 ↓
same Candidate replay
```

不修改：

```text
Plan
Art
Candidate lineage
```

只有 infra retry budget 耗尽后才通知用户：

```text
系统暂时无法完成运行环境执行
```

而不是建议修改策划。

---

# 32. Art Confirm 支持回到 Plan

调整原 Non-Goal。

新 `ART_CONFIRM`：

```text
SELECT_ART_A
SELECT_ART_B
REVISE_ART
REVISE_PLAN
CANCEL_RUN
```

典型场景：

用户看到 Art 以后发现：

> 角色太多，我其实只要 3 个。

这是 Scope / Plan 问题，而不是 Art Prompt 问题。

不应要求 Cancel Run。

---

# 33. 新的 HITL UI

QA Recovery 卡片建议展示：

```text
开发未通过
```

下面分成：

### 失败分类

```text
当前判断：策划能力与运行环境不匹配
```

### 关键证据

```text
- 多次构建失败
- 当前运行环境不支持实时多人同步
- 当前方案资源需求超出单局预算
```

### 系统建议

```text
建议将：
3D → 2D
实时多人 → 单人
开放世界 → 小型地图
```

用户可编辑建议。

操作：

```text
[按建议调整策划]
[再次尝试实现]
[取消生成]
```

内部对应：

```text
REVISE_PLAN
RETRY_IMPLEMENTATION
CANCEL_RUN
```

---

# 34. Replan 后用户确认

任何新的：

```text
PlanRevision
```

即使由 FailureReport 自动生成，也必须重新：

```text
PLAN_CONFIRM
```

禁止系统自动：

```text
P1
 ↓ failure
P2
 ↓ automatically code
```

因为 P2 很可能修改：

* 核心玩法；
* Scope；
* 视觉；
* Session Length；
* 验收标准。

这是用户语义变更。

---

# 35. Replan 后下游处理

P0 默认：

```text
P2 created
 ↓
old Art = STALE
old Candidate = STALE
 ↓
PLAN_CONFIRM
 ↓
regenerate Art
 ↓
ART_CONFIRM
 ↓
new Candidate
```

P1 增加：

```text
Art dependency fingerprint
```

如果：

```text
A1 compatible with P2
```

可以：

```text
reuse A1
```

但必须由系统判定，不让用户通过非结构化选择破坏 invariant。

---

# 36. 数据持久化建议

当前：

```text
RunCheckpoint = PostgreSQL SoT
Redis = Cache
```

继续保留。

但 Checkpoint 不再承担全部历史职责。

最小建议新增：

```text
runs

run_commands

decision_requests

artifacts

failure_reports

outbox_events
```

---

## 36.1 大 Payload

大对象：

* Design Doc
* Art spec
* generated code bundle
* browser traces
* screenshots
* full logs

不建议全部塞 PostgreSQL JSON。

推荐：

```text
Object Storage
```

PG 保存：

```text
URI
hash
size
schema_version
metadata
```

小型结构化对象可以继续 JSONB。

---

# 37. RunCheckpoint 的定位

RunCheckpoint 只回答：

> 当前工作流执行到哪里？

例如：

```json
{
  "active_plan_revision_id": "plan_4",
  "active_art_revision_id": "art_5",
  "active_candidate_revision_id": null,

  "phase": "plan_confirm",

  "workflow_version": 13,

  "revision": 42
}
```

而：

> 为什么来到这里？

由：

```text
RunCommand
RunEvent
FailureReport
```

解释。

---

# 38. 可观测性

所有关键事件统一包含：

```text
run_id
command_id
decision_request_id
workflow_version
plan_revision_id
art_revision_id
candidate_revision_id
failure_report_id
execution_id
```

不存在的字段置空。

---

## 38.1 关键 Metrics

建议至少：

```text
forge_replan_total

forge_replan_success_total

forge_replan_per_run_histogram

forge_failure_class_total

forge_code_retry_total

forge_infra_retry_total

forge_artifact_stale_total

forge_promotion_rejected_total

forge_decision_stale_total

forge_command_redelivery_total

forge_command_idempotent_skip_total

forge_outbox_pending

forge_outbox_publish_latency

forge_run_cost_after_replan
```

---

## 38.2 关键产品指标

需要回答：

```text
多少 qa_failed 最终通过 replan 成功？

用户点击 REVISE_PLAN 后完成率是多少？

Replan 平均多消耗多少 Token？

多少 Replan 实际改变了 Capability Requirements？

多少 Art 能通过 Fingerprint 安全复用？

Replan 2 次以上的成功率是多少？
```

这些指标决定未来是否值得做：

```text
auto degradation
art reuse
automatic scope reduction
```

---

# 39. Event / Audit

建议建立最小 Run Event：

```json
{
  "event_type": "PLAN_REVISED",
  "run_id": "...",
  "command_id": "...",

  "from_plan_revision_id": "plan_3",
  "to_plan_revision_id": "plan_4",

  "reason": "CAPABILITY_MISMATCH",

  "created_at": "..."
}
```

至少记录：

```text
PLAN_CREATED
PLAN_REVISED
PLAN_APPROVED

ART_CREATED
ART_SELECTED
ART_STALE

CANDIDATE_CREATED
CANDIDATE_STALE

QA_FAILED
QA_PASSED

DECISION_REQUESTED
DECISION_RESOLVED

COMMAND_STARTED
COMMAND_COMPLETED

PROMOTION_REJECTED
RUN_COMPLETED
```

Event 不一定第一期做完整 Event Sourcing。

它是 Audit Log，不是新的 SoT。

---

# 40. 测试策略

原方案仅测试 Happy Path 不足。

生产发布前至少覆盖以下。

---

## 40.1 Unit Tests

### Command Vocabulary

```text
allowed command
invalid command
legacy decision mapping
```

### Failure Classification

```text
infra
implementation
capability
resource
acceptance
```

### Dependency Fingerprint

```text
visual fields change → changed
gameplay-only fields change → unchanged
canonical ordering → stable
```

### Promotion Guard

所有 invariant 单独测试。

---

# 41. HITL 并发测试

必须覆盖：

### 双击

```text
same DecisionRequest
same command
```

只生成一次。

### 两个浏览器

```text
Browser A resolves
Browser B resolves old revision
```

B：

```text
409 STALE_DECISION
```

### 旧 WebSocket 卡片

Run 已前进后 Resolve：

```text
409
```

---

# 42. 消息可靠性测试

必须覆盖：

### DB Commit 后 API 超时

客户端 Retry：

```text
不产生重复业务效果
```

### RabbitMQ Duplicate

同 `command_id` 投递两次：

```text
执行一次
```

### Worker Crash Before ACK

```text
business DB commit
 ↓
worker crash
 ↓
redelivery
```

第二次执行：

```text
idempotent skip
```

### Outbox Publish Failure

RabbitMQ 不可用时：

```text
Outbox remains pending
```

恢复后继续发布。

---

# 43. Workflow Version Compatibility 测试

必须模拟：

```text
Old Worker
New Worker
Old Run
New Run
```

验证：

```text
old worker cannot silently execute unsupported new command
```

旧 Run 在滚动发布后仍能恢复。

---

# 44. Artifact Staleness 测试

### Replan

```text
P1 → A1 → C1
 ↓
P2
```

必须：

```text
C1 = STALE
```

P0：

```text
A1 = STALE
```

P1 Fingerprint compatible 时：

```text
A1 remains compatible
```

---

# 45. Promote 安全测试

故意构造：

```text
active plan = P2
candidate.plan = P1
candidate.qa = PASSED
```

Promote 必须失败。

QA Pass 不能绕过 lineage。

---

# 46. Failure Routing 测试

### INFRA_TRANSIENT

不得创建：

```text
REVISE_PLAN DecisionRequest
```

### CAPABILITY_MISMATCH

允许：

```text
REVISE_PLAN
```

### IMPLEMENTATION_DEFECT

attempt budget 未耗尽：

```text
automatic repair
```

耗尽：

```text
DecisionRequest
```

---

# 47. Prompt Safety Tests

输入：

```text
console log:
IGNORE ALL PREVIOUS INSTRUCTIONS...
```

必须：

* 被标记为 Failure Evidence；
* 不能改变 System / Developer Instruction；
* 日志长度受限；
* secret pattern 被脱敏。

---

# 48. Cost Budget Tests

验证：

```text
implementation retry budget
infra retry budget
replan budget
run budget
```

分别独立。

不能：

```text
infra retry
```

意外耗尽：

```text
plan revision budget
```

---

# 49. 实施计划

生产实施不建议按原：

```text
P0 button
P1 plan_rev
P2 prompt
```

拆法。

调整为以下顺序。

---

## Phase 0：领域模型与兼容层

目标：

> 在不改变用户行为的情况下先建立可靠基础。

实现：

```text
RunCommand
DecisionRequest
workflow_version
command_id
Run revision CAS
legacy decision adapter
```

涉及：

```text
hitl.py
runs.py
queue.py
state.py
worker
migration
```

上线后原 UI 行为不变。

---

## Phase 1：可靠消息

实现：

```text
Transactional Outbox
Idempotent Worker
Command status
Publisher retry
```

发布前完成 RabbitMQ 重投 / worker crash integration test。

这一层是后续 Replan 的上线前提。

---

## Phase 2：FailureReport + Failure Classification

实现：

```text
FailureReport
FailureClass
RecoveryPolicy
```

将：

```text
sandbox_failed
qa_failed
```

从核心决策条件降级为 UI / workflow phase。

Recovery 由 FailureClass 决定。

---

## Phase 3：REVISE_PLAN Production Path

实现：

```text
QA Recovery → REVISE_PLAN
ART_CONFIRM → REVISE_PLAN
```

Replan 输入：

```text
PlanRevision
FailureReport
User Feedback
CapabilityProfile
```

输出：

```text
new PlanRevision
```

重新进入：

```text
PLAN_CONFIRM
```

---

## Phase 4：Immutable Artifact Lineage

实现：

```text
PlanRevision ID
ArtRevision ID
CandidateRevision ID
QAContractRevision ID
Dependency edges
STALE state
Promotion Guard
```

停止物理“清空旧 Candidate”。

---

## Phase 5：Capability Precheck

实现：

```text
CapabilityProfile
RequiredCapabilities
CapabilityValidator
Developability Precheck
```

删除 keyword blacklist。

---

## Phase 6：Dependency Fingerprint

实现：

```text
Art reuse
```

仅当：

```text
fingerprint compatible
```

时跳过重新生成 Art。

该阶段属于成本优化，不阻塞核心 Replan 上线。

---

## Phase 7：Observability / Product Optimization

实现：

```text
Replan metrics
Failure metrics
Run cost metrics
Replan UX
Plan change summary
```

根据真实数据决定后续是否：

```text
自动 scope degradation
自动推荐修改
部分资产复用
```

---

# 50. 数据迁移

新字段必须保证旧 Run 可恢复。

建议：

```text
existing runs:
workflow_version = legacy version
```

旧 checkpoint：

```text
没有 artifact revision id
```

恢复时：

```text
legacy adapter
```

禁止上线 Migration 后直接要求所有旧 Run 符合新 Schema。

---

## 50.1 新旧 Run 原则

推荐：

```text
Old Run → Old Workflow Semantics
New Run → New Workflow Semantics
```

不强制把长期暂停中的旧 Run 自动升级为最新工作流。

---

# 51. Rollout

必须灰度。

推荐：

```text
Stage 1
internal accounts

Stage 2
5% new runs

Stage 3
25%

Stage 4
100%
```

监控：

```text
replan error rate
resume error rate
command duplication
outbox lag
run completion rate
cost per completed run
promotion rejection
```

---

# 52. 回滚策略

禁止通过数据库删除新字段回滚。

回滚顺序：

```text
1. Disable new REVISE_PLAN DecisionRequest exposure
2. Stop assigning new workflow_version
3. Existing new-version runs continue on compatible workers
4. Revert UI exposure if necessary
```

不能让已经产生：

```text
workflow_version = N
```

的 Run 被旧 Worker 按 `N-1` 业务语义恢复。

---

# 53. 明确不做（Non-Goals）

本方案重新定义 Non-Goals。

## 53.1 本期不迁移 LangGraph Native Interrupt / Persistence

保持现有 PG SoT + RabbitMQ + 外部恢复模型。

这是当前项目范围边界，不代表永久否定。

---

## 53.2 不做 Fully Connected Graph

不把所有节点互相连边。

跨阶段恢复继续使用：

```text
Command
 ↓
route_start
```

架构。

---

## 53.3 不做完整 Event Sourcing

Artifact 与 Command 是正式 SoT。

RunEvent 仅用于：

```text
audit / observability
```

本期不通过 Replay Event 重建整个 Run。

---

## 53.4 不做 Plan Branch / Merge

Plan Revision 是：

```text
P1 → P2 → P3
```

线性历史。

暂不支持：

```text
P2A
P2B
merge
```

---

## 53.5 不做 Art Partial Regeneration

Art 要么：

```text
reuse compatible revision
```

要么：

```text
generate new revision
```

本期不做局部资产 diff / patch。

---

## 53.6 不做 Cross-Run Artifact Sharing

Artifact lineage 仅在同一个 Run 内生效。

跨 Run 模板 / Plan Library / Art Cache 单独设计。

---

## 53.7 不做全自动语义降级

系统可以：

```text
diagnose
suggest
prepare revised plan
```

但涉及用户需求变化的：

```text
REVISE_PLAN
```

必须由用户确认触发。

---

# 54. 已决定问题

原方案开放问题在本方案中直接拍板。

## 54.1 Replan 后旧 Candidate 怎么处理？

**保留，但标记 STALE。**

不 Promote，不删除。

---

## 54.2 Replan 是否无限？

**否。**

独立 `plan_revision_budget`。

---

## 54.3 Art Confirm 是否可以 Replan？

**可以。**

正式支持 `REVISE_PLAN`。

---

## 54.4 美术无关字段怎么判断？

P0：

```text
默认重新生成
```

P1：

```text
Dependency Fingerprint
```

不用手写某几个字段的临时 diff 作为长期规则。

---

## 54.5 Plan Confirm Modify 与 QA Replan 是否合并？

**底层统一为 `REVISE_PLAN`。**

区别由 Context 决定。

例如：

```text
source = PLAN_CONFIRM
failure_report_id = null
```

与：

```text
source = QA_RECOVERY
failure_report_id = F123
```

共用 Revision Pipeline，不维护两套实际业务实现。

---

## 54.6 Sandbox Failed 是否直接提供 Replan？

**不直接绑定。**

由：

```text
FailureClass
```

决定。

只有语义失败才允许 Replan。

---

## 54.7 是否需要 Feature Flag / Version Gate？

**需要。**

至少：

```text
workflow_version
+
rollout gate
```

---

# 55. 最终状态机

高层用户状态：

```text
PLAN
 ↓
PLAN_CONFIRM
 ├── APPROVE_PLAN
 │       ↓
 │      ART
 │
 └── REVISE_PLAN
         ↓
        PLAN

ART_CONFIRM
 ├── SELECT_ART
 │       ↓
 │      CODE
 │
 ├── REVISE_ART
 │       ↓
 │      ART
 │
 └── REVISE_PLAN
         ↓
        PLAN

CODE / QA
 │
 ├── PASS
 │      ↓
 │   PROMOTION GUARD
 │      ↓
 │     DONE
 │
 └── FAIL
        ↓
   Failure Classification
        │
        ├── INFRA_TRANSIENT
        │       ↓
        │   AUTO RETRY
        │
        ├── IMPLEMENTATION_DEFECT
        │       ↓
        │   CODE REPAIR
        │
        └── SEMANTIC / CAPABILITY FAILURE
                ↓
          DecisionRequest
             ├── RETRY_IMPLEMENTATION
             ├── REVISE_PLAN
             └── CANCEL_RUN
```

---

# 56. 系统最终不变量

以下 invariant 作为生产级实现的硬要求。

## Run

```text
一个 Run 同时最多一个有效 Execution Mutation。
```

## Decision

```text
一个 DecisionRequest 最多成功 Resolve 一次。
```

## Command

```text
一个 command_id 最多产生一次业务效果。
```

## Plan

```text
PlanRevision 不可原地修改。
```

## Artifact

```text
历史 Artifact 不因新版本生成而删除。
```

## Dependency

```text
任何 Artifact 必须明确记录其依赖版本。
```

## Failure

```text
触发 HITL 的 FailureReport 必须在暂停前冻结。
```

## Promotion

```text
STALE Artifact 永远不能 Promote。
```

## Workflow

```text
Worker 不能使用自己不支持的 workflow_version 执行 Run。
```

## Recovery

```text
Infra Recovery 不改变用户语义；
任何改变用户语义的 Recovery 必须经过 HITL。
```

---

# 57. 验收标准

本方案上线的 Definition of Done：

* [ ] QA Exhausted 后用户能够选择 `REVISE_PLAN`
* [ ] Art Confirm 能够选择 `REVISE_PLAN`
* [ ] Infra Transient Failure 不要求用户修改策划
* [ ] Replan 输入包含稳定的 FailureReport，而非临时读取当前错误
* [ ] 新 Plan 以新的 immutable Revision 写入
* [ ] 旧 Plan / Art / Candidate 不被删除
* [ ] 不兼容 Artifact 自动变为 STALE
* [ ] STALE Candidate 无法 Promote
* [ ] HITL 双击不会产生重复 Command
* [ ] 两个浏览器同时 Resolve 只有一个成功
* [ ] RabbitMQ 重复投递不会重复产生 Artifact
* [ ] Worker 在 DB Commit 后、ACK 前 Crash 可以安全恢复
* [ ] RabbitMQ 暂时不可用不会导致 Resume 丢失
* [ ] 新旧 Worker 滚动发布期间旧 Run 可以安全恢复
* [ ] Capability Mismatch 可以在 Plan 阶段提前发现
* [ ] REVISE_PLAN 有独立预算限制
* [ ] Failure Log 进入 LLM 前执行清洗、截断与脱敏
* [ ] 所有关键链路包含 `run_id / command_id / artifact_revision_id`
* [ ] Promotion Guard 有完整集成测试
* [ ] Replan 成功率、成本、失败分类都有监控指标

---

# 58. 最终决策

本次改造不定义为：

> 给 `qa_failed` 增加一个“回炉策划”按钮。

正式定义为：

> **GameForge Workflow Recovery & Artifact Lineage 第一阶段建设。**

保留当前 LangGraph + PostgreSQL + Redis + RabbitMQ + Sandbox 架构骨架。

需要正式建立以下领域能力：

```text
RunCommand
DecisionRequest
FailureReport
FailureClass
RecoveryPolicy
PlanRevision
QAContractRevision
ArtRevision
CandidateRevision
Artifact Dependency
Promotion Guard
Workflow Version
Transactional Outbox
CapabilityProfile
```

其中上线优先级最高的是：

```text
1. RunCommand / DecisionRequest
2. Transactional Outbox + Idempotency
3. FailureReport / Failure Classification
4. REVISE_PLAN Recovery
5. Immutable Artifact Revision + Promotion Guard
6. Workflow Versioning
7. Capability Validation
```

Dependency Fingerprint 与 Art Reuse 属于后续成本优化，不应阻塞核心正确性上线。

最终架构原则：

> **不要把失败当成“退回旧状态”，而应把失败视为生成新版本的证据。**

> **不要删除旧产物，而应通过血缘和状态判断它是否仍然有效。**

> **不要依赖 phase 猜测用户意图，而应使用具有业务语义的 Command。**

> **不要依赖消息只投递一次，而应保证重复投递也只产生一次业务效果。**

> **不要等到 Code 重试三轮后才判断策划能不能做，应尽可能在昂贵阶段之前进行 Capability Validation。**

这套模型建立后，未来新增：

```text
开发退回美术
美术退回策划
切换实现引擎
失败后缩减 Scope
历史版本重新生成
换模型重新实现
从旧 Candidate Fork
不同 Runtime Profile 重跑
```

都可以建立在同一套 Command、Failure、Revision、Dependency 与 Recovery 模型上，而不需要继续向 `route_start()` 中增加越来越多不可维护的 `if/else`。
