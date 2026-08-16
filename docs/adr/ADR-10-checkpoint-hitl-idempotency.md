# ADR-10: Checkpoint, HITL & Idempotency

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P1-5/6/7, P2-2/4/7/12；修订衔接 [ADR-05](./ADR-05-recoverable-pause-representation.md)；[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

---

## Context

可恢复暂停已有 ADR-05，但实现上：promote 幂等「先标记后提交」、用户暂停检查点过窄、resume grant 过早消费、HITL phase 词表多文件复制、checkpoint Redis/DB 双写但 revision 未校验、`resolve_hitl` 锁与竞态写在 API 层。

**核实：** `graph.py` promote / `user_pause` / `resume_grant` 路径属实；`api/runs.py` 与 `graph.py` 各维护 HITL 集合属实。

## Decision

### 1. Promote 幂等两段式（P1-5）

1. Side-effect 幂等采用 **begin / commit**（或「commit 成功后再置完成标记」）：DB 提交失败或进程崩溃后，重放必须能再次 promote 或能检测到「候选版本已是 current」而非永久跳过。
2. else「已执行」分支必须校验 DB 实际版本（或等价事实）后再宣称成功。

### 2. 暂停检查点合并语义（P1-6）

1. `build_pause_checkpoint`（及所有写入方）统一：**读取现有 state，再覆盖少量字段**；禁止只写 `design_doc` 丢掉 art/code/qa 进度。
2. 图内暂停与 `games/services` 暂停共用同一合并函数，消除双语义。
3. `user_pause` 恢复路由按检查点 phase/进度续跑，不得无条件强制回 `art_options` 重烧已确认美术。

### 3. Resume grant 与 RUNNING 回收（P1-7）

1. `resume_grant` 消费延迟到「已离开 HITL 集合的首个成功推进」之后；或提供可重建的一次性凭证语义，避免「grant 已吃、消息被当陈旧跳过、run 永 RUNNING」。
2. Scheduler 增加 RUNNING 超时回收：租约丢失且 N 分钟无心跳 → 置 FAILED（可 retry）或可恢复暂停；不得仅回收 PAUSED。

### 4. HITL 词表与域层（P2-2 / P2-7）

1. Phase 集合与 phase→allowed decisions 单点定义在域层（如 `enums` / `hitl` 模块），紧邻 `RunPhase` / `PauseReason`；API / graph / dev / games **只消费不复制**。
2. `resolve_hitl` / 通用 resume 的锁、校验、入队下沉 services，与 `cancel_run` / `retry_run` 并列；禁止 API 路由内 80 行状态机。
3. 通用 `/resume` 不得在 `art_confirm` 等阶段静默代选决策。

### 5. Checkpoint 缓存一致性（P2-4）

1. `load_state` 优先 Redis 时必须比对 DB `revision`（或等价）；不一致则弃缓存读 DB。
2. 或改为 **事务 commit 成功后再写 Redis**，并提供 invalidate；禁止「DB 回滚后 Redis 残留幻影 grant」。

### 6. resolve 锁与条件提交（P2-12）

1. 防重锁包 try/finally（或等价释放），避免异常后 60s 误 409。
2. 状态迁移用条件 UPDATE（`WHERE status=PAUSED`）或 version 乐观锁，禁止无条件覆盖已 FAILED/已回收的 run。

## Consequences

* 暂停/恢复/重放行为对用户可预测；减少「DONE 但旧版本」「永 RUNNING」。
* 域层收口会触及 `api/runs.py` 与 `graph.py` 较大移动——需测试护栏。
* Scheduler 回收 RUNNING 可能打断长任务：阈值与阈值必须和 ADR-08/09 租约心跳一致。

## Non-goals

* 更换 LangGraph checkpointer 实现品牌。
* 多区域共享 checkpoint（单区域 Postgres+Redis 足够）。
