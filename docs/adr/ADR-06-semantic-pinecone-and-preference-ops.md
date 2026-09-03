# ADR-06: Semantic Cache (Pinecone) + Preference Ops

> **偏好章节已废弃：** §1 表中「偏好*」行、以及 **§4 偏好：检索 / 删除 / 抽取**，自 2026-09-02 起 **不再有效**。
> 偏好记忆真相源改为 **[ADR-15](./ADR-15-preference-memory-as-is.md)**（并废弃 ADR-02）。
> **本文件仍 Accepted 的范围仅限：Semantic Cache / Embedding / Pinecone 拓扑（含 Dual Index 修订）。**

* Status: **Accepted**（仅 Semantic Cache）；偏好部分 → **Deprecated → ADR-15**
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: ADR-04、ADR-14（Knowledge RAG / Dual Index）、ADR-15（Preference Memory）、P4 Exact / P4.5 Semantic

---

## 1. TL;DR

| 主题 | 决策 |
| --- | --- |
| Semantic Cache | Pinecone + Exact Redis；**存「节点结果 payload」** 而非整段聊天 transcript |
| 相似度分层 | `<0.85` miss；`[0.85, 0.95)` **丢给轻量 LLM 再推理一次**；`≥0.95` **直接返回缓存结果** |
| Embedding | 默认推荐 **`bge-small-zh-v1.5`**（轻量、中英够用）；需要更高召回可换 **`bge-m3`**（env 配置） |
| ~~偏好表~~ | ~~Postgres；≤50 物理删除~~ → **见 ADR-15** |
| ~~偏好抽取~~ | ~~轻量 chat~~ → **见 ADR-15** |
| 会话向量 | 仍不做 |
| Pinecone 拓扑 | **`gameforge-semantic` 专用于本 ADR**；Knowledge RAG 使用独立 Index `gameforge-knowledge`（ADR-14 §3.1.1，**互不影响**） |

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

> **Deprecated（2026-09-02）。** 全文迁至 [ADR-15](./ADR-15-preference-memory-as-is.md)。以下历史摘要勿再引用：
>
> * 检索 active ≤50；超额物理删除（先 inferred）
> * 抽取仅 LLM；未配置 model → 不写；inferred 不盖 explicit

---

## 5. Flags / Env（默认开启能力，密钥自备）

见 `backend/.env.example`：`PINECONE_*`、`EMBEDDING_*`、`SEMANTIC_CACHE_*`。
偏好抽取 env（`PREFERENCE_EXTRACT_*`）文档归属 **ADR-15**；语义确认 LLM 仍可回退同一套 key（实现细节，非偏好 ADR 范围）。

---

## 6. 实施顺序（已确认）

Phase 0 配置 → 1 Embedding 客户端 → 2 Pinecone + 分层命中 → 3（历史：LLM 偏好抽取，现归 ADR-15）→ 4 metrics。

## 7. 回滚

* `SEMANTIC_CACHE_DIRECT_HIT_ENABLED=false` 或无 Pinecone key → 仅 Exact + shadow
* 偏好抽取回滚 / 关闭行为见 **ADR-15**

---

## Revision 2026-08-26（Dual Index 拓扑；与 ADR-14 对齐）

* Status: **Accepted**（本修订待 Owner 与 ADR-14 一并审批后生效；**正文决策不变**，仅补充 Pinecone 组织方式）
* Related: [ADR-14](./ADR-14-pinecone-rag-knowledge-base.md)

### 8.1 决策：Account 内双 Index

GameForge Pinecone 采用 **两个独立 Index**，按 **业务 workload** 拆分，而非按「知识子类型」拆 Index：

```text
Pinecone Account
│
├── Index: gameforge-semantic     ← 本 ADR Semantic Cache（已有）
│   └── namespace: default          ← 单 namespace；节点隔离靠 metadata filter
│
└── Index: gameforge-knowledge    ← ADR-14 Knowledge RAG（新建）
    └── namespace: global           ← R0/R1；租户私有知识未来另开 namespace
```

| Index | 用途 | 配置入口（实现） |
| --- | --- | --- |
| `gameforge-semantic` | ADR-06 语义缓存 | `PINECONE_HOST` + `PINECONE_NAMESPACE` |
| `gameforge-knowledge` | ADR-14 知识 RAG | `PINECONE_KNOWLEDGE_HOST`（独立 host，见 ADR-14） |

**Semantic Cache 自身不需要多个 namespace**：可缓存节点仅 4 类，隔离由 metadata `node` + `skill_bundle_hash` 完成（§2.2 不变）。

### 8.2 为何 Knowledge 不并入 `gameforge-semantic`

| 维度 | Semantic Cache | Knowledge RAG |
| --- | --- | --- |
| 写入 | Runtime 自动 upsert | Ingestion / Curation 管道 |
| 读取 | top-1 + 阈值 + 可选确认 LLM | Retrieve + Rerank + 注入 |
| 生命周期 | 短、可淘汰 | 长、版本化 |
| Metadata | `node` / `result` / `skill_bundle_hash` | `domain` / `category` / `source_id` … |

二者 **embedding 模型可相同**，但 workload 与治理模型不同，**合并同一 Index 会增加误查、误删与运维耦合风险**。

### 8.3 缓存不受影响（Non-Regression，硬约束）

引入 ADR-14 **不得**改变 ADR-06 语义缓存行为。实现须满足：

1. **专用客户端**：`get_pinecone_store()`（及 `semantic_cache_*`）**仅**连接 `gameforge-semantic`；Knowledge Retriever **禁止**复用该 store 或 `PINECONE_HOST`。
2. **配置隔离**：现有 `PINECONE_*`（除将来文档化的 knowledge 专用项）语义不变；Knowledge 仅读 `PINECONE_KNOWLEDGE_*`。
3. **开关独立**：`knowledge_rag_enabled=false` 时，缓存路径零改动；关闭 RAG 不得触发 semantic 配置迁移或 re-index。
4. **无交叉 query**：Knowledge 检索不得 query `gameforge-semantic`；Cache lookup 不得 query `gameforge-knowledge`。
5. **无交叉 upsert**：Ingestion 不得向 `gameforge-semantic` 写入；Runtime cache store 不得向 `gameforge-knowledge` 写入。
6. **回滚独立**：删除 / 停用 `gameforge-knowledge` Index 不影响 Semantic Cache 命中与 Exact Redis 路径。

### 8.4 修订后后果

* ADR-06 验收与阈值逻辑 **不变**；仅 Pinecone 拓扑在文档层与 ADR-14 对齐。
* 实现 ADR-14 时须新增独立 Knowledge Pinecone 适配层，**不得**在 `pinecone_store.py` 内用 namespace 切换混跑两种 workload（除非拆成两个 factory，且 cache 路径行为与今完全一致）。
* `PINECONE_INDEX=gameforge-semantic` 继续只描述缓存 Index 名称；Knowledge Index 名由 ADR-14 配置项描述。
