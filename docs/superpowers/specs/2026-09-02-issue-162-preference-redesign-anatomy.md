# Issue #162 解构与修改指南

* Date: 2026-09-02
* Issue: [#162 refactor(memory): node-scoped preferences with closed key catalog](https://github.com/ByteTitan-star/AutoGame/issues/162)
* 对照现状: [ADR-15 Preference Memory As-Is](../../adr/ADR-15-preference-memory-as-is.md)
* 用途: 说明该 Issue **怎么写的、每一段在决策什么、你改哪里会改变什么**；便于针对性改文案 / 收窄范围 / 拍板争议点。

> 本文 **不是** 实现规格。改完 Issue 后若方向稳定，应另写 `docs/superpowers/specs/…-preference-redesign-design.md`，再开实现 PR。

---

## 1. 一句话定位

| 维度 | 内容 |
| --- | --- |
| Issue 类型 | **架构 / 产品意图工单**（enhancement），不是「已可直接编码的小修复」 |
| 写什么 | 现行失败模式 + **目标态方向** + 验收清单 + 非目标 |
| 刻意不写什么 | 完整 migration SQL、最终 API OpenAPI、实现计划步骤（留给 design spec / PR） |
| 与 ADR-15 关系 | ADR-15 = **As-Is**；#162 = **To-Be**。二者不得混成一篇 |

标题用 Conventional Commits 风格：`refactor(memory): …`，暗示破坏性数据模型调整，而非纯 feat 贴皮。

---

## 2. 全文结构地图（按金字塔）

Issue 正文遵循仓库习惯的 **Purpose → Background → Proposed → Non-goals → Impact → Verification → References → Follow-ups**。

```text
Purpose          ← 为什么开单 + 本单边界（只定方向，不实现）
Background       ← 现状怎么坏的（对应 ADR-15）
  ├ Current design
  └ Failure mode
Proposed         ← 目标态（你主要改这里）
  ├ Data model
  ├ Write
  ├ Read
  └ Candidate catalog
Non-goals        ← 明确不做，防 scope creep
Impact & Risks   ← 迁移 / API / ADR / Eval / UI
Verification     ← 可勾选验收（实现完成标准）
References       ← 代码与旧 ADR（现应指向 ADR-15）
Suggested follow-ups ← design spec → PR 顺序
```

**改 Issue 时的经验法则：**

* 改 **产品/架构意图** → 动 `Proposed` + 必要时同步 `Verification` / `Non-goals`
* 改 **问题描述是否准确** → 动 `Background`（应与 ADR-15 一致）
* 改 **本单是否包含实现** → 动 `Purpose` 最后一句 + `Suggested follow-ups`
* 改 **目录槽位** → 只动 `Candidate catalog`（Issue 已标明 starter，可在 design 再定）

---

## 3. 逐段拆解（原文意图 → 你可改的旋钮）

### 3.1 Purpose

**原文在说：**

1. 生产上开放 `(category, key)` 导致 **key drift**，upsert 失效、冲突行堆积。
2. 注入把 **全部** active 偏好塞进每个节点。
3. 本 Issue **只 scope 目标 redesign**（DB + extract + load）；实现是后续 PR/plan，需 design sign-off。

**隐含决策：** #162 是 **设计跟踪单**，Close 条件可以是「design 合并 / 实现合并」——原文偏前者，但 Verification 勾选项像实现完成。**这里有张力，建议你改文案二选一：**

| 选项 | Purpose 结尾怎么写 | Close 何时勾 Verification |
| --- | --- | --- |
| A. 纯设计单 | 「本单 Accept 目标态；实现另开」 | Verification 挪到 design/PR；本单只留「design 文档合并」 |
| B. 设计+实现跟踪 | 「本单跟踪到实现落地」 | 保持现有 checklist，Close = 全部勾完 |
| C. Epic | 拆子 Issue：design / migration / extract / loader / eval | 本单做索引，子单各挂 Verification |

### 3.2 Background · Current design

**对应 ADR-15 的压缩版：**

* 表 `user_preferences`，唯一键 `(user_id, category, key)`，开放字符串
* 写：LLM extract → `upsert_preferences_from_text`；inferred 不盖 explicit **仅精确键匹配**
* 读：全量 active → ContextBuilder
* Cap：全局 ≤50，先删旧 inferred

**你若发现与代码不符：** 先改 ADR-15，再改本段（避免 Issue 与 ADR 双真相）。

**建议补丁（文档一致性）：** 把「ADR-02 / P1」改为「**ADR-15**（As-Is；原 ADR-02 / ADR-06 偏好已废）」。

### 3.3 Background · Failure mode

三条失败模式是 **论证 why change** 的核心：

| # | 模式 | 只靠「node 分桶」能否修 | Issue 结论 |
| --- | --- | --- | --- |
| 1 | Key drift / 重复插入 | **不能** | 必须 **封闭 catalog + 写前归一化** |
| 2 | 过宽注入 | **能** | node 过滤即可 |
| 3 | 野外叙事 key | 部分 | catalog 从根上禁止 |

**你可改的点：**

* 是否保留第 3 条作为证据（本地 DB 观察）——可改成「匿名化样例」或删掉以免过度承诺「已观测」
* 是否把「token 浪费」升级为 P0（影响 Verification 优先级）

### 3.4 Proposed · Data model

**核心拍板项（改这里等于改产品）：**

| 字段 | 原文意图 | 待你确认的歧义 |
| --- | --- | --- |
| `node` | 仅 `play` \| `art` 两枚举 | 要不要 `global` / `code`？跨切「像素」是否只落 `art`？ |
| `key` | 每 node 封闭目录中的 slot | catalog 谁维护？版本化吗？ |
| 去掉 `category` | Optional | **建议你拍板：保留 category 还是删除**——原文两边都留了口 |
| 唯一键 | `(user_id, node, key)` | 与旧 `(user, category, key)` 迁移映射表谁写 |
| retention | 「ADR-02 精神不变」 | 现应写「**ADR-15 保留规则不变**」 |

### 3.5 Proposed · Write

**意图流水线：**

```text
Plan 路径抽取 → 只写 node=play
Art 路径抽取 → 只写 node=art
LLM 只能输出该 node allowlist
服务端：alias → allowlist → 未知 drop|staging → UPSERT
inferred 不盖同 (node,key) 的 explicit
clear-all 仍清两 node
倾向 per-node cap，而非全局一袋
```

**你必须拍板的开口：**

1. **未知 key：`drop` 还是 `staging`？**（Verification 写了「never land in active」，staging 需另表/另 status）
2. **per-node cap 数值？** 全局 50 拆成 25+25 还是各 50？
3. **Plan 里出现美术话术**（「像素风」）——只写 art？双写？丢弃？原文扔给 design：「dual-write policy if needed」。

### 3.6 Proposed · Read

| Graph 节点族 | 加载 |
| --- | --- |
| `plan*` | `node=play` |
| `art*` | `node=art` |
| code / repair | **默认不注入偏好**（靠 design_doc） |

**可改旋钮：** code 是否永远不注入；若以后要「代码风格偏好」是否开第三 node（原文 Non-goals 倾向先不开）。

### 3.7 Non-goals

三件明确不做：

1. 不用「按节点存原始用户原文」替代偏好槽（对话已有 ForgeMessage/summary）
2. 不用 embedding 模糊合并当主键身份
3. 不允许 node 桶内继续开放任意 key

**改 Non-goals = 改范围。** 若你想做 fuzzy merge 辅助迁移，应写成「仅 migration 一次性工具」，并仍留在 Non-goals 的 runtime 路径之外。

### 3.8 Candidate catalog（starter）

```text
art:  style, palette, mood, ui
play: genre, difficulty, pacing, session_length
alias 例: theme|aesthetic|look → style
```

原文标明 **starter — finalize in design/PR**。
改 Issue 时：若你已有定稿目录，直接替换并删「starter」；若未定，保持 starter，避免把未敲定的目录写进 Verification。

### 3.9 Impact & Risks

| 风险点 | 含义 | 你改 Issue 时注意 |
| --- | --- | --- |
| Migration | 旧自由 category/key 要映射 / 归档 / 丢弃 | 建议在 Issue 里 **选定一种默认策略**（否则实现会卡住） |
| API 破坏 | `/me/preferences` shape 变 | 是否需要版本化或兼容层——原文未定 |
| ADR | 原文写修 ADR-02/06 | **应改为：修订/增补 ADR-15，或新 ADR-16 To-Be** |
| Eval #124 | 场景与 runner 改 `(node,key)` | 与实现同 PR 或硬依赖 |
| 设置 UI | 按 node+slot 编辑 | 前端是否在本 Epic 内——原文未拆 |

### 3.10 Verification（验收清单）

现行 6 条均可测试化，对应目标态不变量：

1. 同义词 → 同一 `(user,node,key)` 行
2. Art 仅 art / Plan 仅 play
3. 未知 key 不进 active
4. inferred 不盖 explicit
5. clear 双 node + per-node cap
6. eval + migration 文档更新

**建议你增补（若选 B 实现跟踪）：**

* [ ] ADR-15 增加「Superseded by ADR-XX」或另立 To-Be ADR
* [ ] OpenAPI / 前端设置页与新 shape 对齐
* [ ] 回滚方案（feature flag 或只读旧表）

### 3.11 References / Follow-ups

* References 应把 ADR-02/06 偏好改为 **ADR-15**，并保留代码路径列表。
* Follow-ups 顺序合理：`specs/` 设计 → migration → extract contract → loader → API/eval。
  **不要**在未改 Purpose 的情况下把实现细节塞进 Issue 正文（会变成无法评审的超长单）。

---

## 4. 与 ADR-15 / 旧 ADR 的引用怎么改

| 旧写法（#162 原文） | 建议改成 |
| --- | --- |
| Current design (ADR-02 / P1) | Current design (**ADR-15**) |
| ADR-02 / ADR-06: retention… amendment | **Amend ADR-15** 或 **新开 ADR-16（To-Be）**；Semantic Cache 仍 ADR-06 |
| docs/adr/ADR-02-… | `docs/adr/ADR-15-preference-memory-as-is.md` |

---

## 5. 推荐你优先拍板的 8 个问题（改 Issue 前）

按优先级：

1. 本单是 **纯设计** / **设计+实现** / **Epic 拆子单**？（§3.1）
2. `category` 列：**删除**还是保留？（§3.4）
3. 未知 key：**drop** 还是 **staging**？（§3.5）
4. 跨 node 偏好（「像素」）：只 `art` / 双写 / 禁止在 play 抽取？（§3.5）
5. per-node cap 数字？（§3.5）
6. code/repair：**永不**注入偏好？（§3.6）
7. 旧数据迁移默认：**映射表** / **归档只读** / **一次性清空**？（§3.9）
8. To-Be 文档形态：**改 ADR-15** 还是 **新 ADR-16**？（§3.9）

把答案写回 `Proposed` / `Non-goals` / `Impact` 对应段落即可；不必先写代码。

---

## 6. 最小修改模板（可直接贴回 GitHub）

若你只想先做「文档对齐 + 澄清本单边界」，可用下面骨架替换 Purpose / References 相关句（其余 Proposed 等你拍板后再改）：

```markdown
## Purpose

Track a preference memory redesign required by production behavior: open
`(category, key)` strings cause key drift; injection loads all active prefs
into every node. This issue records the **target architecture** (DB + extract +
load). **Implementation is out of scope until** a design spec under
`docs/superpowers/specs/` is signed off. Close criteria for *this* issue:
design accepted (link). Implementation tracked in follow-up PR/issues.

## Background

### Current design (ADR-15)
- …（保持原 bullet，标题改 ADR-15）

## Impact & Risks
- **ADR-15:** retention/extract spirit stays; document node+catalog as
  amendment **or** ADR-16 To-Be (choose one in design).
- **ADR-02 / ADR-06 preference sections:** already deprecated; do not amend.

## References
- `docs/adr/ADR-15-preference-memory-as-is.md`
- （其余代码路径不变）
```

---

## 7. 自检清单（你改完 Issue 后）

- [ ] Purpose 的 Close 条件与 Verification 勾选项一致（无「设计单却挂实现验收」矛盾）
- [ ] Background 与 ADR-15 无冲突
- [ ] Proposed 中每个「Optional / decide in design」要么拍板，要么显式留在 design 待办
- [ ] Non-goals 覆盖你担心被误加的范围
- [ ] Impact 写清迁移默认策略与 API 兼容策略
- [ ] References 不再把 ADR-02 当有效偏好 ADR
- [ ] 标题仍准确（若从 redesign 缩成「仅加 node 过滤不加 catalog」，应改标题）

---

## 8. 相关文件

| 文件 | 角色 |
| --- | --- |
| [ADR-15](../../adr/ADR-15-preference-memory-as-is.md) | 现状真相 |
| [ADR-02](../../adr/ADR-02-preference-retention.md) | 已废弃 |
| [ADR-06](../../adr/ADR-06-semantic-pinecone-and-preference-ops.md) | 仅缓存有效；偏好章节已废 |
| Issue #162 | 目标态意图 |
| Issue #124 | 偏好 eval（实现后需跟 schema） |
