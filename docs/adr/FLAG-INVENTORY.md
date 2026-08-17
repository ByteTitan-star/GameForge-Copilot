# Forge Runtime Feature Flag Inventory

* Status: Defaults after Owner Accept (ByteTitan-star, 2026-08-16)
* Related: [ACCEPT-CHECKLIST.md](./ACCEPT-CHECKLIST.md)、[ADR-06](./ADR-06-semantic-pinecone-and-preference-ops.md)

| Flag | Default | Notes |
| --- | --- | --- |
| `sandbox_backend` | `daytona` | 无 `DAYTONA_API_KEY` 时工厂回退 docker→local |
| `sandbox_daytona_enabled` | `true` | Key 仍只来自环境变量 |
| `sandbox_tier_auto` | `true` | 启发式/telemetry 选档，非 Agent 随意指定 |
| `sandbox_default_tier` | `standard` | auto 关闭或无强信号时的基线 |
| `memory_preferences` | `true` | |
| `memory_preferences_inferred` | `true` | 不覆盖 Explicit；正式路径仅 LLM 抽取 |
| `memory_preferences_max_active` | `50` | 超额**物理删除**最早 inferred→explicit |
| `memory_session_summary` | `true` | |
| `memory_session_summary_llm` | `true` | 失败回落确定性 |
| `skills_router_enabled` | `true` | 节点只看见本节点 Skill |
| `skills_llm_selection` | `true` | LLM 只看 name/description；Policy 强制 |
| `skills_quality_lift_llm` | `true` | 评估用 |
| `exact_cache_enabled` | `true` | Redis 精确缓存（生产命中路径） |
| `semantic_cache_shadow_enabled` | `true` | Redis 影子样本（标定） |
| `semantic_cache_direct_hit_enabled` | `true` | 允许分层命中；无 Pinecone/embed 则空操作 |
| `semantic_cache_soft_threshold` | `0.85` | 低于此 miss |
| `semantic_cache_hard_threshold` | `0.95` | ≥ 此直接返回；中间带需 LLM 确认 |
| `embedding_enabled` | `true` | 无 key/base_url → 不 embed |
| `embedding_model` | `bge-small-zh-v1.5` | 轻量默认；可换 `bge-m3` |
| `pinecone_enabled` | `true` | 需 `PINECONE_API_KEY` + `PINECONE_HOST` |
| `preference_extract_enabled` | `true` | 无 `PREFERENCE_EXTRACT_MODEL` → 不自动抽取 |

## 明确禁止

* 规则引擎作为偏好抽取**正式路径**（`explicit.py` / `inferred.py` 仅保留单元测试/遗留，生产走 LLM）
* 硬编码 `DAYTONA_API_KEY` / `PINECONE_API_KEY` / Embedding key 进仓库
* 高熵节点（plan/art/code/…）语义 direct hit
* 会话 transcript / 偏好表写入 Pinecone（v1）
