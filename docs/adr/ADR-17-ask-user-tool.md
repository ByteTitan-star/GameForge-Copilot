# ADR-17: On-demand HITL — ask_user as a Model-invoked Tool

* Status: **Accepted**
* Date: 2026-09-11
* Accepted-by: ByteTitan-star（owner 提案：HITL 不灵活，应作为工具按需调用；偏好已含答案则不问）
* Related: [ADR-05](./ADR-05-recoverable-pause-representation.md)（暂停表示）、[ADR-10](./ADR-10-checkpoint-hitl-idempotency.md)（HITL/幂等）、[ADR-16](./ADR-16-preference-memory-to-be.md)（偏好记忆 = "不问"的信号源）、Issue [#169](https://github.com/ByteTitan-star/GameForge-Copilot/issues/169)
* Complements: 现有固定确认门（plan_confirm / art_confirm）继续保留——它们守晋升，ask_user 守信息。

---

## 0. Owner 决策（签字记录）

1. **方向**：HITL 从"指定节点触发"演进为"模型按需调用的工具"；核心判据是**偏好/上下文已有足够信息就不问**。
2. **实现形态**：inline JSON 工具协议（单条结构化输出，平台解析），不依赖厂商 function-calling——LLM 层尚无工具调用支持，且 BYOK 下游能力不一。
3. **先落地节点**：plan（澄清需求收益最大）；art/code 视效果后续放开。

## 1. TL;DR

| 主题 | 决策 |
| --- | --- |
| 触发 | 模型在生成时发现**决策关键**信息缺失且无法从 设计稿/会话摘要/偏好 推出 → 输出 ask_user 工具调用而非产物 |
| 协议 | `{"tool":"ask_user","reason":str,"question":str,"options":[str,...],"allow_free_text":bool}` 作为该节点本轮的**完整输出** |
| 暂停 | 新 HITL 相位 `agent_question`（ADR-05 暂停表示 + ADR-10 RunCommand/resume_grant 全复用） |
| 恢复 | 决策 `{skip, modify}` → 既有 `revise_plan` 通道；`modify_text` 即用户回答（自由文本或选项文本）；skip 注入"用户让你自行决策"合成回答 |
| 预算 | `forge_ask_user_max_per_run`（默认 2）；耗尽后不再暂停，注入合成回答"请按偏好与现有信息自行决策"并重跑该节点一次 |
| 不新增 | RunCommandType、恢复幂等机制、WS 事件类型——全部复用 |

## 2. 决策细节

### 2.1 工具契约（写进 plan 系统/用户提示）

* **先查记忆**：MEMORY_DATA（ADR-16 偏好，带 source/confidence）、已确认设计稿、会话摘要——能推导就**不得**提问。
* **可问的判据**：缺失信息会显著改变产物形态（题材方向、核心玩法取舍、内容分级等），且不在上述任何来源中。
* **禁止**：偏好已覆盖的维度（风格/难度/语言等）再问；一次输出多个问题；把 ask_user 当逃生舱（凡不确定就问）。

### 2.2 服务端护栏

* 解析严格：shape 不符 → 当作普通产物输出（走既有解析失败/diagnose 路径），绝不 crash。
* 预算计数存 checkpoint state（`ask_user_count`），跨 resume 幂等；耗尽自动合成回答并 `resume` 单次重跑。
* 问题与回答全量入 RunCommand（审计）；WS `hitl_wait` 载荷新增 `question` 字段。

### 2.3 前端

`agent_question` 卡片：问题文本 + 选项 chips + 自由文本框 → 复用 resolve 调用（decision=modify / skip）。

## 3. Non-goals

* LLM 层原生 function-calling / 多轮工具循环（另行演进；本协议向前兼容之）。
* 取消既有固定确认门（职责不同：门守晋升，工具守信息）。
* art/code/qa 节点放开提问（后续按数据决定）。

## 4. 验收（对应 issue #169）

* 有效工具 JSON → 暂停为 agent_question 且载荷含 question/options；坏 JSON 不炸不暂停。
* 回答经 revise 通道注入 plan 重跑；skip 注入合成回答。
* 预算内第二次提问正常暂停；耗尽后自动继续不再暂停。
* 既有确认门与全量测试不受影响。
