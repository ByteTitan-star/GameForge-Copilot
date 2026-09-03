# ADR Index

Accepted Architecture Decision Records for Forge Runtime evolution.
Full narrative lives in [2026-08-15-forge-runtime-evolution-plan.md](../2026-08-15-forge-runtime-evolution-plan.md).

Design-review follow-up (verify + modification guide):
[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

| ADR | Title | Status | Accepted-by |
| --- | --- | --- | --- |
| [ADR-01](./ADR-01-degraded-artifact-publishing.md) | Degraded Artifact Publishing | **Accepted** | (prior) |
| [ADR-02](./ADR-02-preference-retention.md) | Preference Retention | **Deprecated** → [ADR-15](./ADR-15-preference-memory-as-is.md) | ByteTitan-star |
| [ADR-03](./ADR-03-sandbox-provider-strategy.md) | Sandbox Provider Strategy | **Accepted** (+ 2026-08-16 revision) | ByteTitan-star |
| [ADR-04](./ADR-04-conversation-storage-migration.md) | Conversation Storage Migration | **Accepted** | ByteTitan-star |
| [ADR-05](./ADR-05-recoverable-pause-representation.md) | Recoverable Pause Representation | **Accepted** (+ 2026-08-16 revision) | ByteTitan-star |
| [ADR-06](./ADR-06-semantic-pinecone-and-preference-ops.md) | Semantic Cache (Pinecone)；偏好章节已废 | **Accepted**（仅缓存）；偏好 → ADR-15 | ByteTitan-star |
| [ADR-07](./ADR-07-production-security-baseline.md) | Production Security Baseline | **Accepted** | ByteTitan-star |
| [ADR-08](./ADR-08-worker-messaging-reliability.md) | Worker & Messaging Reliability | **Accepted** | ByteTitan-star |
| [ADR-09](./ADR-09-timeout-and-io-boundaries.md) | Timeout & IO Boundaries | **Accepted** | ByteTitan-star |
| [ADR-10](./ADR-10-checkpoint-hitl-idempotency.md) | Checkpoint, HITL & Idempotency | **Accepted** | ByteTitan-star |
| [ADR-11](./ADR-11-sandbox-hosting-resources.md) | Sandbox & Hosting Resources / SoT | **Accepted** | ByteTitan-star |
| [ADR-12](./ADR-12-api-frontend-ops-debt.md) | API, Frontend & Ops Debt | **Accepted** | ByteTitan-star |
| [ADR-13](./ADR-13-native-engine-agent-loop.md) | Native Engine Agent Loop（Godot-first） | **Proposed** | （待审批） |
| [ADR-14](./ADR-14-pinecone-rag-knowledge-base.md) | Pinecone RAG Knowledge Base | **Proposed** | （待审批） |
| [ADR-15](./ADR-15-preference-memory-as-is.md) | Preference Memory（As-Is） | **Accepted**（取代 ADR-02 / ADR-06 偏好） | （Owner 审阅） |

Sign-off record: [ACCEPT-CHECKLIST.md](./ACCEPT-CHECKLIST.md)
Feature flag defaults: [FLAG-INVENTORY.md](./FLAG-INVENTORY.md)

## ADR-14 附录（实施 / 评审）

| 文档 | 说明 |
| --- | --- |
| [ADR-14-implementation-status-brief.md](./ADR-14-implementation-status-brief.md) | ADR-14 **实施状态与生产就绪评审**（Living；Production NO-GO；Gap Matrix / Readiness Gate） |

## Proposed（未来规划，待 Owner 审批）

* **任务 1 / ADR-13**：原生引擎 Agent 闭环（生成→编译→运行→日志→修复），Godot 优先，Unity 后期。
* **任务 2 / ADR-14**：Pinecone RAG — `gameforge-knowledge`（`global` namespace + domain/category metadata）；与 ADR-06 `gameforge-semantic` **双 Index 隔离**，配置与客户端分离，**不影响语义缓存**。
