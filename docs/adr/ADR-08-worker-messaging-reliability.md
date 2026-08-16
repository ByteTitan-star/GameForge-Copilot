# ADR-08: Worker & Messaging Reliability

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P0-3, P1-1～4, P1-8, P1-9；[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

---

## Context

Worker 承担 `execute_run` / `resume_run`、邮件与 outbox。审查确认：容器无 restart、长 run 与 RabbitMQ `consumer_timeout` 冲突、decode/DLQ 失败可丢消息、租约 busy 热循环、崩溃重投不读 checkpoint、邮件与长任务共池。

**核实：** 上述机制在 `docker-compose.yml`、`messaging/worker.py`、`forge/graph.py` 属实。

## Decision

### 1. 进程存活（P0-3）

1. Compose（及等价编排）中 `worker` 与 `backend` 设置 `restart: unless-stopped`（或平台同等策略）。
2. `_consume()` 外层捕获异常，带指数退避重连，禁止「一次异常进程退出且永不回来」。

### 2. Ack 与长任务（P1-1）

任选其一并文档化为唯一策略（推荐先做 A，中期演进 B）：

* **A（短线）：** RabbitMQ 显式配置 `consumer_timeout` ≥ 最大 run 预算（含 code_qa 外墙），并监控接近阈值的 run。
* **B（目标态）：** 快速 ack + 执行租约 + 独立看门狗；消息确认与 run 生命周期解耦。

禁止长期维持「默认 30 分钟 consumer_timeout + 整 run 占着 unacked」而不改任一侧。

### 3. 消息不丢（P1-2）

1. `decode_task` 与业务处理同属可观测失败路径：非法消息记日志后进 DLQ（或明确 reject 策略），禁止未 await 的 Task 异常。
2. `_republish_task` / `_publish_to_dlq` 包 try/except；DLQ 发布失败时降级本地落盘（或等价持久化），并告警。

### 4. 租约 busy 与失败重试（P1-3 / P1-9）

1. `TaskLeaseBusy`：**禁止**固定 `sleep(2)` + 原 `retry_count` 无限重投。改为延迟重投（x-delay / 延迟队列）或递增计数 + 指数退避，并设上限后进 DLQ。
2. 普通失败重试同样带退避；提供 DLQ 重放脚本或运维手册步骤。
3. SMTP 客户端显式 timeout。

### 5. 崩溃重投与 checkpoint（P1-4）

1. Broker 重投（`redelivered`）或 run 已为 `RUNNING` 的重复 `execute_run`：必须走 checkpoint 恢复语义（`load_state`），不得从 plan 无条件整图重烧。
2. 与 ADR-10 的 grant/幂等决策一致：重跑不得靠「新 execution_id」绕过用户可感知的重复计费。

### 6. 队列隔离（P1-8）

1. 邮件类任务（验证码、重置密码）使用 **独立队列**（独立 consumer 或同进程独立 channel + prefetch）。
2. 长 run 占满游戏任务 prefetch 时，不得阻塞验证码投递超过产品 SLA（建议目标：秒级，而非分钟级）。

## Consequences

* Worker 崩溃可自动恢复；消息丢失面缩小。
* 可能增加 RabbitMQ 配置复杂度与延迟队列依赖。
* 重投改走 checkpoint 后，部分「看起来像重新开始」的行为会变为续跑——前端文案需一致。

## Non-goals

* 多区域跨机房消息总线。
* 替换 RabbitMQ 为其它 broker（除非另开 ADR）。
