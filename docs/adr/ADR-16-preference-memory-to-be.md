# ADR-16: Preference Memory（To-Be / Canonical Catalog + Policy + Resolver）

* Status: **Accepted**
* Date: 2026-09-11
* Accepted-by: ByteTitan-star（owner 决策见 issue #162 2026-09-11 评论）
* Related: [ADR-15](./ADR-15-preference-memory-as-is.md)（As-Is，保持不变）、Issue [#162](https://github.com/ByteTitan-star/GameForge-Copilot/issues/162)、[#124](https://github.com/ByteTitan-star/GameForge-Copilot/issues/124)（eval）
* Supersedes: ADR-15 所描述实现的目标态部分（ADR-15 继续作为迁移前 As-Is 真相源）

---

## 0. Owner 决策（签字记录）

1. **冲突策略**：issue/ADR 与 owner 决策冲突时改文档（issue #162 的 cap 章节已同步修订）。
2. **淘汰 = 归档**：活跃上限 50；按 `last_used_at` 最旧归档，**explicit 不豁免**；归档行 agent 永不可见、仅供维护审计；永不物理 DELETE。
3. **LRU 心跳**：`last_used_at` 在每次注入（resolve_for）与每次复确认抽取时刷新。
4. **架构**：单一 Preference Service（闭集目录 + 类型化槽位 + 操作式抽取 + 服务端策略裁决）为唯一读写路径；agent 工具前门推迟到 LLM 层支持 function-calling 后（服务层无需改动）。
5. **注入分域**：目录 `applies_to` 决定节点可见性；code/repair 默认不注入偏好。
6. **字段投影**：热路径只读 `preference_key/value/source/confidence`；`note`（触发语句摘录）只写不读，仅供审计；不注入自由文本（防持久化提示注入）。

## 1. TL;DR

| 主题 | 决策 |
| --- | --- |
| 身份 | `(user_id, preference_key)`，key 为**闭集目录槽位 id**（如 `visual.style`） |
| 值 | 按目录类型校验（enum/bool/number/短串）；拒绝任意自由对象 |
| 写入 | 操作式抽取（`{op: set\|remove\|touch, key, value, source, confidence}`）→ 服务端策略裁决 |
| 合并 | 同 key：explicit 恒胜；inferred 仅当置信度 ≥ 现值（或现值为 inferred 且更旧）可更新 |
| 读取 | `resolve_for(node)`：applies_to ∩ node；注入带 source+confidence |
| 淘汰 | LRU 归档（见 owner 决策 2/3） |
| 前门 | 现阶段：异步抽取（平台模型）；将来：agent 工具（同服务层） |

## 2. 数据模型

新表 `user_preferences_v2`（旧表 `user_preferences` 保留为迁移源，随后废弃）：

```sql
UNIQUE (user_id, preference_key)
preference_key TEXT   -- 目录槽位 id
value TEXT            -- 合法枚举名 / 标量文本
value_type TEXT       -- enum | bool | number | string
source TEXT           -- explicit | inferred
confidence REAL       -- 0~1
status TEXT           -- active | archived（归档 = agent 不可见，仅审计）
last_used_at TIMESTAMPTZ
note TEXT DEFAULT ''  -- 触发语句截断摘录（≤120 字符），只写不读
```

## 3. 目录（PREFERENCE_CATALOG，代码内字典）

```yaml
visual.style:        {type: enum, applies_to: [art, plan], values: [pixel, pixel_retro_gb, neon, flat, cartoon, realistic, minimalist]}
visual.palette:      {type: enum, applies_to: [art], values: [dark, light, warm, cool, pastel, high_contrast]}
visual.mood:         {type: enum, applies_to: [art, plan], values: [cheerful, calm, epic, eerie, cute]}
ui.style:            {type: enum, applies_to: [art], values: [minimal, hud_heavy, retro]}
ui.language:         {type: enum, applies_to: [art, plan], values: [zh, en]}
gameplay.genre:      {type: enum, applies_to: [plan], values: [platformer, shooter, puzzle, racing, roguelike, tower_defense, slice, runner]}
gameplay.difficulty: {type: enum, applies_to: [plan], values: [easy, normal, hard, hardcore]}
gameplay.pacing:     {type: enum, applies_to: [plan], values: [relaxed, standard, intense]}
gameplay.session_length: {type: enum, applies_to: [plan], values: [short, medium, long]}
audio.muted:         {type: bool, applies_to: [plan], values: [true, false]}
```

别名归一（服务端，写路径第一步）：`theme|aesthetic|look → visual.style`、`配色|color → visual.palette`、`难度 → gameplay.difficulty` 等；未命中别名且不在目录 → **拒绝进入 active**（P0）。

## 4. 写路径（操作式抽取）

抽取模型输入 = 用户消息 + 现有活跃偏好摘要（key/value/source/confidence 四字段投影，不过滤节点）。
输出协议（仅建议，服务端裁决）：

```json
{"operations": [{"op": "set", "key": "visual.style", "value": "pixel", "source": "explicit", "confidence": 1.0}]}
```

* `set`：新增/更新（走合并策略）
* `remove`：用户明确否定（"别再默认暗色"）→ 归档
* `touch`：意图命中现值，仅刷新 `last_used_at`
* 契约要求区分**长期偏好**与**当前任务指令**（"这次简单点" ≠ 偏好），prompt 明示 + 服务端对单条消息高频翻转做防抖（同 key 短窗口内第二次翻转忽略）

服务端策略（最终裁决，规则可测）：

1. 别名归一 → 目录校验 → 类型校验；任一失败丢弃该操作并计数（可观测）
2. 合并：同 key 时——现值 explicit 且新值 inferred → 仅 touch；其余按置信度与新旧覆盖
3. 淘汰：写入后活跃数 > 50 → 按 `last_used_at` 最旧归档

## 5. 读路径

`resolve_for(db, user_id, node)`：4 字段投影 + `status='active'` + 目录 `applies_to ∩ {node}`；随后对命中 key 批量 touch（一条 UPDATE）。
ContextBuilder 渲染：`[MEMORY] visual.style = pixel (explicit, 1.0)`；`plan*`/`art*` 经 resolver，`code`/`repair` 默认无偏好注入。
目录槽位静态提示（服务端策划常量，可选、默认关）：渲染时追加固定短语，**不注入任何用户衍生自由文本**。

## 6. 迁移与兼容

一次性脚本（`backend/scripts/migrate_preferences_v2.py`）：旧行 `(category, key)` 经别名表归一——
命中目录 → 写 v2 active（source/confidence 保留，note 记"migrated"）；未命中 → v2 archived（note 记原始 key）。
旧表只读保留一个发布周期后废弃。`/me/preferences` 改为目录键形态（破坏性，契约同步）。

## 7. Non-goals

* 偏好归属写为图节点行 / 同事实按节点双写
* 向量库作为偏好身份或检索
* 目录任何桶内开放 key
* org/workspace/game 多级作用域继承
* agent 工具前门（待 LLM 层 function-calling）

## 8. 验收（对应 issue #162）

* 同意图不同别名 → 归一后仅一行 `(user_id, preference_key)`
* 未知 key 永不进 active；类型不符拒绝
* inferred 不覆盖 explicit（仅 touch）
* cap 按 last_used_at 归档，永不物理 DELETE；归档行 resolve 不可见；注入/复确认刷新 last_used_at
* art 只见 applies_to 含 art 的偏好，plan 同理；code/repair 无注入
* 注入行含 source+confidence；eval #124 数据集改用目录键
