# Forge Runtime Feature Flag Inventory

* Status: Operator reference（默认值偏安全；改生产前对照 ADR / 计划 Go·No-Go）
* Related: [ACCEPT-CHECKLIST.md](./ACCEPT-CHECKLIST.md)、evolution plan

| Flag | Default | Risk if flipped | Notes |
| --- | --- | --- | --- |
| `sandbox_backend` | `local`（生产应 `docker`） | 隔离失效 / 出境 | ADR-03；勿默认 `e2b` |
| `sandbox_e2b_enabled` | `false` | 源码出境 | 需 `--extra e2b` + key |
| `sandbox_tier_auto` | `false` | 过降档导致 OOM | 开后读 engine/体量/近期失败 |
| `memory_context_builder` | `true` | 关则不注入 recent turns | 仍走 ContextBuilder |
| `memory_context_enforcement` | `true` | 兼容残留；不再切 concat | concat 已拆除 |
| `memory_preferences` | `true` | 关则无 Explicit 注入 | |
| `memory_preferences_inferred` | `false` | 弱信号污染 | 不覆盖 Explicit |
| `memory_session_summary` | `true` | | |
| `memory_session_summary_llm` | `false` | 额外费用 | 失败回落确定性 |
| `skills_router_enabled` | `true` | | Policy 始终注入 |
| `skills_llm_selection` | `false` | 费用 / 误选 | Policy 永不 LLM |
| `skills_quality_lift_llm` | `false` | 付费 A/B | 无 complete 则退回 mock |
| `exact_cache_enabled` | `true` | | 仅白名单节点 |
| `semantic_cache_shadow_enabled` | `false` | Redis 膨胀 | **禁止** direct hit |
| `reliability_node_timeout` | `true` | | |
| `reliability_idempotent_side_effects` | `true` | 重复副作用 | |

## 明确禁止（无 flag 可开）

* Semantic Cache **direct hit**（`semantic_direct_hit_allowed()` ≡ False）
* 生产默认 `sandbox_backend=e2b`（须 ADR-03 Accept + benchmark 表填满）
