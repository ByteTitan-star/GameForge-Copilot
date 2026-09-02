# ADR-15: Preference Memory（As-Is / 现行设计）

* Status: **Accepted**（现行实现真相源；**取代**已废弃的 ADR-02 与 ADR-06「偏好」章节）
* Date: 2026-09-02
* Accepted-by: （Owner 审阅中；以代码为准）
* Related: Issue [#162](https://github.com/ByteTitan-star/AutoGame/issues/162)（目标态 redesign，**非**本 ADR）、[#124](https://github.com/ByteTitan-star/AutoGame/issues/124)（eval）
* Supersedes: [ADR-02](./ADR-02-preference-retention.md)、[ADR-06](./ADR-06-semantic-pinecone-and-preference-ops.md) §4 偏好相关决策

> **范围：** 本文只描述 **当前已落地** 的用户长期偏好记忆（User Preference Memory）。
> **不包含：** Semantic Cache / Pinecone（仍见 ADR-06 缓存章节）、Session Summary、Knowledge RAG。
> **目标态**（node 分桶 + 封闭 key catalog）见 Issue #162，未 Accept 前 **不得**当作现行行为。

---

## 1. TL;DR

| 主题 | 现行决策 |
| --- | --- |
| 作用域 | **用户级**长期记忆；删 Game **不删**偏好；「清空偏好」删该用户全部行 |
| 身份键 | `(user_id, category, key)`；`category` / `key` 均为 **开放字符串**（无 allowlist） |
| 来源 | `source=explicit`（明确）\| `inferred`（弱推断）；**inferred 不得覆盖同键 explicit** |
| 写入 | ① API `PUT /me/preferences`（强制 explicit）② Plan/Art 路径 LLM 抽取（ADR-06 时代约定，现归本 ADR） |
| 抽取 | **仅轻量 chat LLM**；未配置 `preference_extract_*` → **不写库**；规则引擎不是正式路径 |
| 读取 / 注入 | `list_active_preferences` 拉 **全部** active 行 → ContextBuilder 注入 Plan/Art 等节点（**不按节点过滤**） |
| 上限 | active ≤ `memory_preferences_max_active`（默认 50）；超额 **物理删除** 最早 inferred，再删最早 explicit |
| 注入语义 | 偏好是 **MEMORY_DATA**，不得当 instruction（防注入文案由 ContextBuilder 固定前缀保证） |

---

## 2. Context

Forge 需要跨 Game / 跨会话记住用户的长期创作偏好（如「像素风」「偏难」），并在后续 Plan / Art 等节点注入上下文。

既有文档曾拆成：

* ADR-02：保留策略（Explicit 不随删 Game 消失等）
* ADR-06 §4：抽取只用 LLM、active 限额

二者过短且与实现细节脱节，生产上已暴露 **开放 key 漂移** 与 **全量注入过宽**（见 #162）。本 ADR 把 **现行实现** 收成单一真相源；目标态 redesign 另开 Issue / 后续 ADR。

---

## 3. Decision（现行）

### 3.1 数据模型

表：`user_preferences`（`backend/app/models/user_preference.py`）

| 列 | 含义 |
| --- | --- |
| `id` | UUID PK |
| `user_id` | FK → `users.id` ON DELETE CASCADE |
| `category` | 开放字符串，最长 64 |
| `key` | 开放字符串，最长 64 |
| `value_json` | JSON object |
| `source` | `explicit` \| `inferred`（约定；DB 未 enum 强制） |
| `confidence` | float，默认 1.0 |
| `status` | 默认 `active`（列表 API / 注入只读 active） |
| `created_at` / `updated_at` | 时区时间 |

**唯一约束：** `uq_user_pref_user_cat_key` = `(user_id, category, key)`
**索引：** `(user_id, status)` 点查 active。

**没有：** node 维度、key allowlist、alias 归一化、staging 表。

### 3.2 保留与生命周期

1. **Explicit / Inferred 均为 user-scoped**，不绑定单个 Game。
2. **删除 Game 不删除** 该用户的偏好行（测试：`test_preferences_survive_game_delete`）。
3. **Clear my preferences**（`DELETE /me/preferences`）删除该用户 **全部** 行（含 inactive）。
4. 用户账号 CASCADE 删除时，偏好一并删除。

### 3.3 Explicit vs Inferred

| 规则 | 行为 |
| --- | --- |
| API PUT | 一律 `source=explicit` |
| LLM 抽取 | 模型输出 `source`；非法值回落 `inferred` |
| 冲突 | 若已存在 `source=explicit` 同行，新来的 `inferred` **跳过、不写** |
| 同键更新 | 同 `(category, key)` 的后续 upsert **覆盖** `value_json` / `source` / `confidence` / `status`（explicit 可覆盖 inferred；inferred 不可覆盖 explicit） |
| 开关 | `memory_preferences_inferred=false` 时丢弃 LLM 产出的 inferred 项 |

### 3.4 写入路径

```text
用户消息 / API body
        │
        ├─ PUT /api/v1/me/preferences ──► upsert_preference(source=explicit)
        │
        └─ graph Plan/Art compose
                │
                ▼
        upsert_preferences_from_text
                │  memory_preferences == false → []
                ▼
        extract_preferences_via_llm
                │  未配置 model/apikey 或开关关 → []
                ▼
        逐条：inferred 保护 → upsert_preference → _enforce_active_cap
```

**Graph 触发点**（`backend/app/forge/graph.py`）：

* `_compose_plan_input`：刷新 session summary → 偏好抽取 → `build_node_context(node="plan")`
* `_compose_art_input`：同上，`node="art"`

抽取与注入都在 compose 阶段发生；**code / repair 等节点**若走 ContextBuilder，同样可能带上全部偏好（见 3.6）。

### 3.5 LLM 抽取契约

文件：`backend/app/forge/memory/llm_extract.py`

* System prompt 要求只输出：

```json
{"preferences":[{"category":str,"key":str,"value_json":object,"source":"explicit"|"inferred","confidence":0-1}]}
```

* **无**服务端 category/key 白名单；解析仅校验：非空 category/key、`value_json` 为 object、source 二选一。
* 失败（JSON 坏、LLM 异常）：返回 `[]`，**静默不写**（打 warning 日志）。
* `kind="preference_extract"`，走 `platform_complete`；`max_tokens=512`。

配置（`app/core/config.py` / `.env`）：

| 配置 | 默认 | 作用 |
| --- | --- | --- |
| `memory_preferences` | true | 总开关；关则 upsert_from_text 直接空 |
| `memory_preferences_inferred` | true | 是否接受 inferred |
| `memory_preferences_max_active` | 50 | active 物理上限 |
| `preference_extract_enabled` | true | 抽取开关 |
| `preference_extract_provider` | openai_compat | |
| `preference_extract_model` | `""` | **空则不抽取** |
| `preference_extract_apikey` | `""` | **空则不抽取** |
| `preference_extract_base_url` | `""` | 可选 |

遗留：`explicit.py` / `inferred.py` 仍有规则启发式，**正式写库路径不得依赖**；兼容函数 `upsert_explicit_from_text` / `upsert_inferred_from_text` 均转发到 LLM 路径。

### 3.6 读取与 Context 注入

1. `list_active_preferences(user_id)`：`status == "active"`，**无 category/node 过滤**。
2. `loader.build_node_context`：若 `memory_preferences`，把全部 active 行转成 dict 交给 `ContextBuilder`。
3. `ContextBuilder`：
   * 格式：`- {category}.{key}={value_json}` 列表
   * 段落标题：`【Explicit Preferences】`（文案未区分 inferred，但行内带 `source` 字段在 dict 中；格式化行 **未打印 source**）
   * 固定前缀声明 MEMORY_DATA，禁止当指令执行
   * 预算：preferences 约占 `memory_context_budget_tokens` 的 5%；超预算时与其它段一起裁剪

**现行行为：** Plan 与 Art（及一切走 `build_node_context` 且开偏好的节点）看到的是 **同一袋** 全量偏好。

### 3.7 Active 上限

`_enforce_active_cap`：

1. 取全部 active；若 `len ≤ cap` 返回。
2. 排序键：`(0 if inferred else 1, updated_at|created_at)` —— inferred 优先删、同组删更旧。
3. **物理 DELETE** 溢出行（非改 status=inactive）。

### 3.8 HTTP API

前缀：`/api/v1/me/preferences`（`backend/app/api/preferences.py`）

| Method | 行为 |
| --- | --- |
| GET | 当前用户 active 列表 |
| PUT | body: `category`, `key`, `value_json`, 可选 `status`；写入 `source=explicit` |
| DELETE | clear 全部行；返回 `{deleted: n}` |

Schema：`backend/app/schemas/preferences.py`（开放 category/key，长度 1–64）。

### 3.9 与 Session Summary / 对话的边界

| 机制 | 作用域 | 是否长期偏好 |
| --- | --- | --- |
| `user_preferences` | 用户 | 是 |
| `game.session_summary_json` | 单 Game 会话摘要 | 否 |
| `ForgeMessage` | 单 Game 对话 | 否（证据，非偏好槽位） |

偏好抽取吃的是 **当次用户文本**；不替代 summary / recent turns。

---

## 4. 已知局限（As-Is 事实，非目标态）

下列是现行设计的结构性后果，**不是**实现 bug 的独家名单；产品/架构 redesign 由 #162 跟踪。

1. **Key drift：** LLM 对同一意图可产出不同 `(category, key)`（如 `style` vs `theme`）→ 唯一键对不上 → INSERT 多行 → 矛盾偏好同时注入。
2. **过宽注入：** 无 node 过滤；Art 可收到玩法难度类偏好，Plan 可收到纯美术槽位，浪费 token 并可能干扰生成。
3. **开放 schema 漂移：** 野外已可见叙事式 key（如 `artistic_style.visual_expressiveness`），难治理、难做设置页稳定编辑。
4. **格式化丢 source：** 注入文本行未展示 `source`/`confidence`，模型难以区分强弱信号。
5. **无未知 key 拒收：** 抽取结果只要字段形状合法即入库。

---

## 5. Consequences

* 新会话 / 新 Game：只要同一 `user_id`，即可注入 ≤50 条 active 偏好。
* 运维：未配抽取模型时「看起来开了 Memory」但永不自动写偏好——属预期。
* 评测：`eval/runners/preference_eval.py` / `#124` 按现行 `(category, key)` 契约编写；目标态变更后必须改数据集与 runner。
* 文档：ADR-02、ADR-06 偏好章节 **废弃**；对外引用偏好记忆时 **只引用本 ADR**。Semantic Cache 仍引用 ADR-06 缓存章节（或后续独立 ADR）。

---

## 6. 代码地图

| 职责 | 路径 |
| --- | --- |
| 模型 | `backend/app/models/user_preference.py` |
| 存储 / 上限 / upsert | `backend/app/forge/memory/preferences.py` |
| LLM 抽取 | `backend/app/forge/memory/llm_extract.py` |
| 装配入口 | `backend/app/forge/memory/loader.py` |
| 注入拼装 | `backend/app/forge/memory/context_builder.py` |
| Graph 触发 | `backend/app/forge/graph.py`（`_compose_plan_input` / `_compose_art_input`） |
| HTTP | `backend/app/api/preferences.py` |
| 配置 | `backend/app/core/config.py`（`memory_preferences*` / `preference_extract_*`） |
| 测试 | `backend/tests/forge/memory/test_*preferences*`、`test_preferences_api.py` |

---

## 7. Verification（现行行为验收口径）

* [ ] 同 `(user, category, key)` upsert 更新而非重复插入。
* [ ] inferred 不覆盖已有 explicit。
* [ ] active 超过 cap 时先删旧 inferred。
* [ ] 删 Game 后偏好仍在；`DELETE /me/preferences` 全清。
* [ ] 未配置 extract model/apikey 时自动路径不写库。
* [ ] Plan/Art compose 后 Context 含 `【Explicit Preferences】`（有数据时）。

---

## 8. 修订记录

| 日期 | 变更 |
| --- | --- |
| 2026-09-02 | 初版：汇总现行实现；废弃 ADR-02 与 ADR-06 偏好决策 |
