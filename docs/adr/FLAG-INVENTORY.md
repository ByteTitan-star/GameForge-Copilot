# Forge Runtime Feature Flag Inventory

* Status: Defaults after Owner Accept (ByteTitan-star, 2026-08-16)
* Related: [ACCEPT-CHECKLIST.md](./ACCEPT-CHECKLIST.md)

| Flag | Default | Notes |
| --- | --- | --- |
| `sandbox_backend` | `e2b` | 无 `E2B_API_KEY` 时工厂回退 docker→local |
| `sandbox_e2b_enabled` | `true` | Key 仍只来自环境变量 |
| `sandbox_tier_auto` | `true` | 启发式/telemetry 选档，非 Agent 随意指定 |
| `sandbox_default_tier` | `standard` | auto 关闭或无强信号时的基线 |
| `memory_preferences` | `true` | |
| `memory_preferences_inferred` | `true` | 不覆盖 Explicit |
| `memory_preferences_max_active` | `50` | 超额归档最旧 inferred→explicit |
| `memory_session_summary` | `true` | |
| `memory_session_summary_llm` | `true` | 失败回落确定性 |
| `skills_router_enabled` | `true` | 节点只看见本节点 Skill |
| `skills_llm_selection` | `true` | LLM 只看 name/description；Policy 强制 |
| `skills_quality_lift_llm` | `true` | 评估用 |
| `exact_cache_enabled` | `true` | Redis 精确缓存（生产命中路径） |
| `semantic_cache_shadow_enabled` | `true` | Redis 影子样本；**无 Pinecone；无 direct hit** |

## 明确禁止

* Semantic Cache **direct hit**（`semantic_direct_hit_allowed()` ≡ False）
* 硬编码 `E2B_API_KEY` 进仓库
