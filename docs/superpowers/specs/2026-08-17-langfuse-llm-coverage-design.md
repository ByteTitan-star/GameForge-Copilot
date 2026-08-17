# Langfuse LLM 全覆盖 + Session 聚合设计

* 日期：2026-08-17
* 状态：已批准，实施中
* 范围档位：**B**（LLM 全覆盖 + `session_id`/`tags`；不含 embedding / Admin 探测）

## 1. 目标

所有业务 LLM 调用（用户配置路径 + 平台旁路路径）均上报 Langfuse generation；主生成 run 用 `session_id=str(game_id)` 聚合多次创作；generation 以业务 `kind` 命名，便于 UI 区分。

## 2. 非目标

* embedding / semantic lookup·store span
* Admin `test_connectivity`
* Langfuse Scores / Prompt Management / Datasets

## 3. 约定

| 项 | 规则 |
|----|------|
| Generation name | `llm:{kind}` |
| metadata | 必有 `kind`、`provider`；有则带 `user_id`/`game_id`/`run_id` |
| session_id | `str(game_id)` |
| tags | 基础 `forge`；场景加 `guardrail` / `memory` / `cache`；可选 `phase:{name}` |

### kind 枚举（本轮）

`plan` / `art` / `code` / `qa` / `session_summary` / `skill_select` / `guardrail` / `preference_extract` / `semantic_confirm` / 默认 `chat`

## 4. 架构（方案①）

1. 扩展 `observe_generation(kind=...)`；新增 `propagate_trace_attrs`（包装官方 `propagate_attributes`，无 key no-op）。
2. `observe_run` 接收 `user_id`/`game_id`，内层 propagate session + tags。
3. `call_llm` / `call_llm_stream` 透传 `kind`。
4. 平台旁路（偏好抽取、语义确认）经 `platform_complete`：observe + `provider.complete`，**不**记用户 usage/熔断。
5. Guard 使用 `kind=guardrail`，尽量补齐 ids；tags 含 `guardrail`。

## 5. 测试

* `kind` → generation name；无 key no-op；propagate 无 key 不炸
* platform_complete 走观测；旁路不再裸调 `provider.complete`
* conftest 清空 key 行为不变

## 6. 验收

同一 `game_id` 多次 run 在 Langfuse Sessions 下可见；UI 中可见 `llm:plan` / `llm:guardrail` / `llm:preference_extract` 等；未配置 key 时零外发。
