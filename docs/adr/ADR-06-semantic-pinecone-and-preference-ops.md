# ADR-06: Semantic Cache (Pinecone) + Preference Ops

* Status: **Accepted**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: ADR-02、ADR-04、P4 Exact / P4.5 Semantic

---

## 1. TL;DR

| 主题 | 决策 |
| --- | --- |
| Semantic Cache | Pinecone + Exact Redis；**存「节点结果 payload」** 而非整段聊天 transcript |
| 相似度分层 | `<0.85` miss；`[0.85, 0.95)` **丢给轻量 LLM 再推理一次**；`≥0.95` **直接返回缓存结果** |
| Embedding | 默认推荐 **`bge-small-zh-v1.5`**（轻量、中英够用）；需要更高召回可换 **`bge-m3`**（env 配置） |
| 偏好表 | Postgres；索引点查；**≤50 物理删除最早** |
| 偏好抽取 | **只用轻量 chat 模型**（禁止规则抽取作为正式路径）；配置项对齐审核模型体系，**本阶段以 `.env` 配置为准** |
| 会话向量 | 仍不做 |

---

## 2. 缓存到底存什么？语义检索如何返回？

### 2.1 存储对象（要想清楚的核心）

Semantic / Exact 缓存的是 **白名单「低熵节点」的结构化结果**，不是整轮 Agent 对话：

| node | 存什么（`result`） | 语义检索命中后返回什么 |
| --- | --- | --- |
| `entry_router` | `EntryPhase` 字符串 | 同左 |
| `engine_router` | `engine_id` 字符串 | 同左 |
| `template_selection` | template dict / list | 同左 |
| `intent_classification` / `deterministic_metadata` | 既有 JSON 结果 | 同左 |

Pinecone **vector** = `embed(规范化 query 文本)`  
Pinecone **metadata**（最少）=

```json
{
  "node": "entry_router",
  "skill_bundle_hash": "<sha>",
  "query_text": "<normalized>",
  "result": "<json-serializable payload>",
  "created_at": 1710000000
}
```

Redis Exact 仍存同一 `result`（精确 key）。  
Redis Shadow 仍只记 hash 指纹（标定用）。

**不存**：完整 LLM 聊天消息流、plan/art/code 正文、用户隐私长文。

### 2.2 返回策略（Owner 敲定）

```text
Exact Redis hit? → 直接返回 result
else:
  embed + Pinecone top1 (filter: node + skill_bundle_hash)
  score < 0.85 → miss → 正常计算 → Exact set + Pinecone upsert + shadow
  0.85 ≤ score < 0.95 → 将 (current_query, cached_result, node) 交给「确认 LLM」推理一次
                         → 解析 JSON result → 返回（失败则 miss 重算）
  score ≥ 0.95 → 直接返回 metadata.result（不再调 LLM）
```

「确认 LLM」= 平台配置的轻量 chat（可与偏好抽取共用或分开 env）；输入短、输出必须是该节点允许的 JSON/枚举。

---

## 3. Embedding 选型

| 模型 | 定位 | 建议 |
| --- | --- | --- |
| **`bge-small-zh-v1.5`** | 轻量、中文友好、维度小、便宜快 | **默认推荐**（路由缓存足够） |
| `bge-m3` | 更强多语/长文 | 召回不够时再换 |
| `multilingual-e5-small` | 另一轻量多语选项 | 备选 |
| `text-embedding-3-small` | OpenAI 托管 | 有 OpenAI 账时可用 |

结论：缓存策略 **轻量 embed 即可**；默认写 `bge-small-zh-v1.5`，Owner 在 env 自行改。

---

## 4. 偏好：检索 / 删除 / 抽取

* 检索：`user_id + status=active` + 索引 → ≤50 行，快。
* 超额：**物理删除最早**（先 inferred，再 explicit）。
* 抽取：**禁止规则作为正式路径**；仅轻量 chat 模型抽取 JSON 偏好。  
  - 未配置 `PREFERENCE_EXTRACT_MODEL` → **不自动抽取**（不写偏好）。  
  - Explicit / Inferred 由模型输出 `source` 字段区分；服务端仍强制：不得用 inferred 覆盖已有 explicit。
* 配置：与审核模型同体系字段风格；**本阶段只保证 `.env.example` 完整**，管理后台 UI 可随后补。

---

## 5. Flags / Env（默认开启能力，密钥自备）

见 `backend/.env.example`：`PINECONE_*`、`EMBEDDING_*`、`PREFERENCE_EXTRACT_*`、`SEMANTIC_CACHE_*`。

---

## 6. 实施顺序（已确认）

Phase 0 配置与偏好删除策略 → 1 Embedding 客户端 → 2 Pinecone + 分层命中 → 3 LLM 偏好抽取（替换规则路径）→ 4 metrics。

## 7. 回滚

* `SEMANTIC_CACHE_DIRECT_HIT_ENABLED=false` 或无 Pinecone key → 仅 Exact + shadow  
* 无偏好抽取模型 → 不写自动偏好
