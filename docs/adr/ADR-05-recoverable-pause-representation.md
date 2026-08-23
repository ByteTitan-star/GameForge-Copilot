# ADR-05: Recoverable Pause Representation

* Status: **Accepted**
* Date: 2026-08-15
* Related: P0 Reliability, HITL；[ADR-10](./ADR-10-checkpoint-hitl-idempotency.md), [ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

## Decision

Recoverable pauses use explicit `paused` + `pause_reason` (and checkpoint metadata), not ad-hoc status strings alone.

## Consequences

* Resume / cancel / timeout paths share one pause model.
* Operators and clients can distinguish HITL wait vs infra pause.

---

## Revision 2026-08-16（设计审查后）

* Status: **Accepted**
* Accepted-by: ByteTitan-star
* Date: 2026-08-16

### 新增决策

1. **检查点合并语义：**
   任何暂停写入（图内 `user_pause`、服务层暂停、HITL 暂停）必须 **合并现有 checkpoint**，仅覆盖 phase / pause_reason / 必要字段；禁止只持久化 `design_doc` 导致 art/code/qa 进度丢失。
2. **Phase 词表归属：**
   HITL / resume 相关 phase 集合是域模型的一部分，单点定义并导出；API、graph、dev、games **禁止各维护一份影子集合**（详见 ADR-10）。
3. **与 RUNNING 的边界：**
   「可恢复」不仅指 `PAUSED`：resume grant 消费、租约丢失后的 RUNNING 卡住，必须有回收或可 retry 路径（ADR-10 §3）。ADR-05 原「paused + pause_reason」模型扩展为：**暂停态与可恢复失败态都要机器可区分**。
4. **恢复路由：**
   恢复时按 checkpoint 真实进度续跑；不得把「用户暂停」无条件解释为「回到 art_options 重来」。

### 修订后后果

* ADR-05 仍是暂停**表示**的权威；promote 幂等、grant 时序、resolve 下沉等**机制**以 ADR-10 为实施决策。
* 客户端可用统一 pause_reason / phase 展示「等人 / 等 infra / 可 retry」，减少「假死」误判。
