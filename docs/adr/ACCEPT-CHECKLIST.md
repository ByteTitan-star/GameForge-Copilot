# ADR Accept Checklist（人工签字门禁）

> 本文件**不**把 ADR-02/03/04 标为 Accepted。仅汇总证据，供 Owner/Reviewer 签字后改各 ADR 头状态。

## 总原则

* 代码已按 **Proposed** 草案 interim 落地 ≠ Accept。
* Accept 需要产品/合规/运维明确签字；AI/实现者不得单方改 Status。

---

## ADR-02 Preference Retention

| 检查项 | 证据 / 位置 | 签字 |
| --- | --- | --- |
| Explicit 不随 Game 删除清除 | `memory/preferences.py` + API clear | ☐ |
| Inferred 不覆盖 Explicit；默认 flag 关 | `memory_preferences_inferred=false` | ☐ |
| 用户可见保留文案（设置/清除偏好）已评审 | 前端 copy / 隐私说明 | ☐ |
| 是否需要 `evidence_game_id` 已拍板 | ADR-02 Acceptance criteria | ☐ |

**Accept 阻塞：** 产品/法务文案签字。

---

## ADR-03 Sandbox Provider Strategy

| 检查项 | 证据 / 位置 | 签字 |
| --- | --- | --- |
| 生产默认 Docker | `sandbox_backend` / ADR-03 | ☐ |
| E2B SDK 仅 PoC，默认关 | `sandbox_e2b_enabled`、`--extra e2b` | ☐ |
| Data-flow / 出境风险已评审 | [sandbox-data-flow.md](./sandbox-data-flow.md) | ☐ |
| Benchmark Go 指标未同时满足前不切默认 | [sandbox-e2b-benchmark.md](../sandbox-e2b-benchmark.md) | ☐ |
| HITL destroy+restore 行为符合预期 | `sandbox/lifecycle.py` | ☐ |

**Accept 阻塞：** 运维确认国内网络与成本；合规确认数据流。  
**明确：** Accept ADR-03 ≠ 默认切 E2B。

---

## ADR-04 Conversation Storage Migration

| 检查项 | 证据 / 位置 | 签字 |
| --- | --- | --- |
| `forge_messages` 为会话 SoT | `models/forge_message.py`、`GET` forge messages | ☐ |
| ContextBuilder 只读本 Game 消息 | `memory/loader.py` | ☐ |
| 无并行「第二套会话表」写入正式路径 | 代码检索 / review | ☐ |
| 历史迁移（若有旧表）完成或声明 N/A | 迁移脚本 / 运维 | ☐ |

**Accept 阻塞：** 确认无遗留会话双写；迁移 N/A 或已完成。

---

## 签字区（人工）

| ADR | Reviewer | Date | Decision |
| --- | --- | --- | --- |
| ADR-02 | | | Accept / Defer / Reject |
| ADR-03 | | | Accept / Defer / Reject |
| ADR-04 | | | Accept / Defer / Reject |
