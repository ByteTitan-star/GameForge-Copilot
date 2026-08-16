# ADR-06: Semantic Cache (Pinecone) + Preference Ops

* Status: **Proposed**（待 Owner 确认后实施；确认后改为 Accepted / ByteTitan-star）
* Date: 2026-08-16
* Related: ADR-02（偏好）、ADR-04（会话 SoT）、P4 Exact Cache、P4.5 Semantic
* Owners: ByteTitan-star

---

## 1. 结论摘要（TL;DR）

| 主题 | 决策 |
| --- | --- |
| Semantic Cache | **引入 Pinecone**；Exact Redis 仍先查；语义命中阈值 **≥ 0.85**，**< 0.85 一律 miss**；≥ 0.95 记为 high-confidence 指标（不影响是否返回） |
| Embedding | 默认 **bge-m3**（OpenAI-compat `/embeddings`）；允许管理员换成更轻量 embed 模型（低熵路由缓存可接受） |
| 偏好存储 | **继续 Postgres `user_preferences`**，**不进 Pinecone** |
| 偏好检索性能 | `user_id + status` 索引 + **最多 50 条** → 查询为毫秒级，不是慢路径 |
| 超额策略 | active **> 50 时删除最早**（按 `updated_at`/`created_at` 升序物理删除或硬归档后删除；本 ADR 定：**物理删除 earliest**） |
| 偏好抽取 | MVP 保留规则抽取；增强：**管理员可配「偏好抽取模型」**（与审核模型同页/同配置体系） |
| 会话向量 | **仍不做** Conversation → Pinecone（ADR-04 不变） |

---

## 2. 背景与问题

1. Exact Cache（Redis）只能精确命中；近义改写会 miss。
2. Semantic shadow 只记指纹，不能返回结果。
3. Owner 要求引入 Pinecone + 相似度阈值。
4. Owner 关心：`user_preferences` 是否慢、如何更新、如何抽取、是否要管理后台配模型。

---

## 3. 决策：Semantic Cache + Pinecone

### 3.1 命中链路

```text
白名单节点请求
  → Exact Redis get（精确）
  → miss → embed(query_text)  via embedding_model（默认 bge-m3）
  → Pinecone query top_k=1
       filter: node == X AND skill_bundle_hash == H
  → score < 0.85 → miss（继续算）
  → score >= 0.85 → direct hit（返回 metadata.payload）
  → 计算结果后：Exact set + Pinecone upsert + Redis shadow
```

### 3.2 阈值

| 分数 | 行为 |
| --- | --- |
| `< 0.85` | **不算命中** |
| `≥ 0.85` | **允许 direct hit** |
| `≥ 0.95` | 仍命中；metrics 打 `high_confidence=true`（观测用） |

默认配置：`semantic_cache_similarity_threshold = 0.85`。

### 3.3 范围（写什么进 Pinecone）

**仅 Exact 白名单节点**（与现有一致）：

* `entry_router` / `engine_router` / `intent_classification` / `template_selection` / `deterministic_metadata`

**禁止**：`plan` / `art` / `code` / `repair` / `qa` / `diagnose` / preference 抽取结果本身。

### 3.4 向量与元数据

* **Vector**：embedding(query 规范化文本)
* **Metadata（最少）**：
  * `node`, `skill_bundle_hash`, `payload_json`（或指向 Redis 的 `exact_key`）
  * `created_at`
* **隔离**：第一版 **全局共享**（低熵路由）；不做跨用户偏好混入。若后续要 per-user cache，另开 ADR 增 `user_id` filter。

### 3.5 Embedding 模型

* **默认：`bge-m3`**（多语、质量稳；经现有 OpenAI-compat `base_url` 调用）。
* **轻量模型是否 OK？**  
  **对「白名单低熵路由缓存」可以接受更小 embed 模型**（延迟/成本更低，召回略糙，靠 0.85 阈值兜底）。  
  **不推荐**用超小模型做会话/偏好语义（本 ADR 也不做那两块）。
* 管理员可改 `embedding_model` / `embedding_base_url` / `embedding_apikey`（平台级，类似审核模型）。

### 3.6 降级与密钥

* 无 `PINECONE_API_KEY` 或无 embedding 配置 → **不语义命中**，Exact + shadow 仍可用；进程不崩溃。
* Pinecone / embedding 超时 → miss，走原计算路径。
* 密钥仅环境变量 / 管理后台加密配置，禁止进仓库。

### 3.7 Feature flags（建议默认）

| Flag | 建议默认 | 含义 |
| --- | --- | --- |
| `semantic_cache_shadow_enabled` | true | Redis 影子 |
| `semantic_cache_direct_hit_enabled` | true | 允许 ≥0.85 命中 |
| `semantic_cache_similarity_threshold` | 0.85 | 命中下限 |
| `pinecone_enabled` | true | 总开关（无 key 则空操作） |

---

## 4. 决策：`user_preferences` 检索 / 优化 / 维护

### 4.1 会不会慢？

**不会。** 原因：

* 按用户过滤：`WHERE user_id = ? AND status = 'active'`
* 已有索引：`ix_user_preferences_user_status (user_id, status)`
* **硬上限 50 条** → 结果集极小，排序/注入可忽略

这是典型「主键用户维度的小表点查」，与 Pinecone 无关，也 **不需要** 为偏好建向量索引。

### 4.2 超额策略（本 ADR 修订）

* `memory_preferences_max_active = 50`
* 超出时：**删除最早的记录**（按 `updated_at ASC, created_at ASC`；优先删 `inferred`，再删 `explicit`）
* 与「归档」相比，物理删除更符合 Owner「最早删掉」表述；clear API 仍可一键清空。

### 4.3 如何更新？

| 路径 | 行为 |
| --- | --- |
| Explicit upsert | `(user_id, category, key)` 唯一；同 key 覆盖 value |
| Inferred upsert | 同 key 已是 Explicit → **跳过**；否则写入/更新 |
| 用户清除 | `DELETE /me/preferences` 全删 |
| 管理员 | 可查看/清空（若已有或后续加 admin API） |

### 4.4 如何提取偏好？

**现状（已实现）：**

* Explicit：触发词（以后/我喜欢/默认…）+ 规则 schema（`explicit.py`）
* Inferred：弱规则（`inferred.py`），不覆盖 Explicit

**增强（本 ADR 批准后做）：**

1. **默认仍走规则**（零额外模型费、可测、可回放）
2. **可选 LLM 抽取**：管理员配置「偏好抽取模型」（provider/model/apikey/base_url），类似 **审核模型**  
   - 仅当规则未抽出且文本像偏好时调用（或显式 flag）  
   - 输出 JSON `{category,key,value_json,source}`，校验后写入  
   - **轻量 chat 模型即可**（抽取约束，不是写代码）；不必上大推理模型
3. **管理后台**：在现有 Admin「全局设置 / 审核模型」同体系增加：
   - Embedding 模型（给 Pinecone Semantic Cache）
   - 偏好抽取模型（可选）
   - Pinecone index / namespace / 是否启用 direct hit / 阈值展示（只读或可改）

可以这样做，且与现有 `AuditSection` / `SettingsSection` 扩展一致。

### 4.5 为什么偏好不进 Pinecone？

* 偏好是 **结构化约束**（category/key），SQL upsert + 上限 50 是正确工具。
* 向量化偏好会导致：重复条目、难审计、与 Explicit 不覆盖语义冲突。
* 若未来要「自然语言找回旧偏好」，另开 ADR，且与 Cache 索引 **物理隔离**。

---

## 5. 明确不做（本 ADR Out-of-Scope）

* Conversation / `forge_messages` → Pinecone
* Preference → Pinecone
* 高熵节点（plan/art/code）语义命中
* 无校准就下调阈值到 < 0.85

---

## 6. 实施分期（敲定执行顺序）

### Phase 0 — 文档与配置（本 ADR Accepted 后立即）

* 更新 `FLAG-INVENTORY`、`.env.example`、evolution plan 中 P1.5/P4.5 表述
* 超额策略从「归档」改为「删最早」（代码+测试）

### Phase 1 — Embedding 客户端 + 管理配置

* `app/llm/embeddings.py`（OpenAI-compat embeddings，默认模型名 `bge-m3`）
* 平台设置项：embedding_* （对齐 audit_* 模式）
* Admin UI：设置页增加 Embedding /（可选）偏好抽取模型区块

### Phase 2 — Pinecone Adapter + Semantic direct hit

* optional dep：`pinecone`
* `app/forge/cache/pinecone_store.py`：upsert / query
* 改写 `semantic_cache_lookup`：threshold 0.85；接通 routers 白名单路径
* 无 key / 失败 → miss
* 单测：mock Pinecone + fake embed；禁止 forbidden 节点写入

### Phase 3 — 偏好抽取模型（可选增强）

* `preference_extract_*` 平台配置
* 规则优先，LLM 回退
* Admin 与审核同页配置
* 测试：规则命中不调 LLM；LLM JSON 校验失败回落

### Phase 4 — 观测

* metrics：`semantic_hit_total{band=ge_085|ge_095|miss}`、embed latency、pinecone errors
* 影子样本可对照 false hit（人工抽检）

---

## 7. 验收标准（Go）

* Exact hit 路径不变
* `score < 0.85` 永不返回语义命中
* 无 Pinecone/embedding key 时系统仍可用
* 白名单外节点零 upsert
* 单用户 active 偏好 ≤ 50；第 51 条写入后最早一条被删除
* 管理后台可配置 embedding（及可选偏好抽取模型）

## 8. 回滚

* `pinecone_enabled=false` 或 `semantic_cache_direct_hit_enabled=false` → 回到 Exact + shadow
* 偏好抽取 LLM 关 → 仅规则

---

## 9. 待 Owner 确认后执行

请确认下列选项（可直接回复「按 ADR-06 执行」）：

1. 阈值：**命中线 0.85**，**0.95 仅作高置信指标** — OK？  
2. Embedding 默认：**bge-m3**，允许后台换成轻量模型 — OK？  
3. 偏好超额：**物理删除最早**（而非归档）— OK？  
4. 管理后台：Embedding + 可选偏好抽取模型，挂在设置/审核同体系 — OK？  
5. 实施顺序：Phase 0→1→2→3→4 — OK？

确认后将本 ADR 标为 **Accepted / ByteTitan-star**，再按 Phase 开分支实现（多 commit、单 PR）。
