# Issue #162 解构与修改指南

* Date: 2026-09-02（修订：对齐 Catalog + Resolver 目标态）
* Issue: [#162](https://github.com/ByteTitan-star/AutoGame/issues/162)
* 对照现状: [ADR-15](../../adr/ADR-15-preference-memory-as-is.md)
* 用途: 说明 #162 **现行目标方向**、与旧稿差异、以及后续改文案时动哪一段。

> 本文 **不是** 实现规格。方向稳定后另写 `docs/superpowers/specs/…-preference-redesign-design.md`。

---

## 1. 一句话定位

| 维度 | 内容 |
| --- | --- |
| Issue 类型 | **Epic / 目标态架构跟踪**（enhancement） |
| 核心纠正 | **不要**把 `node` 存成偏好所有权；应用 **canonical `preference_key` + catalog.`applies_to` + Resolver** |
| As-Is | ADR-15（开放 `(category,key)` + LLM 直写 + 全量注入） |
| To-Be | Catalog / Extraction / Policy / Store / Resolution 分层（#162） |

标题方向：`refactor(memory): canonical preference catalog with policy and resolver`（已相对旧标题「node-scoped …」修正）。

---

## 2. 相对旧 Issue 稿的关键变更

| 旧稿 | 现行目标态 |
| --- | --- |
| 唯一键 `(user_id, node, key)` | `(user_id, preference_key)`；key ∈ closed catalog |
| Plan 只写 `node=play` 行 | 抽取归一到 canonical key；**不**按写路径复制 node 行 |
| Art 上下文 = `WHERE node=art` | Resolver：`catalog.applies_to` 含当前 graph node |
| 全局/分 node cap 可删 explicit | **P0：explicit 不因 cap 自动物理删除** |
| LLM → shape check → DB | Candidate → Normalize → Policy → Persist |
| ADR-02/06 amendment | 修订指向 **ADR-15**；To-Be 可另开 ADR-16 |

---

## 3. 正文结构地图

```text
Purpose          ← 三根问题 + P0 边界 + 本单跟踪范围
Background       ← ADR-15 压缩 + failure modes（扩展）
Proposed         ← Catalog / Pipeline / Store / Resolver / Cap 策略
Non-goals        ← 含：禁止 node-owned 行、禁止 vector 主键
Impact & Risks   ← migration / API / ADR-15|16 / eval / security
Verification     ← 按 P0→P1 可测不变量
Priority roadmap ← P0 / P1 / P2 表
References
Follow-ups       ← design spec → 分 PR
```

---

## 4. 分层目标（写入 Proposed 的骨架）

```text
Application (Plan/Art/API/Settings)
        ↓
Preference Service (remember / forget / resolve_for(node) / list)
        ↓
Extraction (LLM → PreferenceCandidate)
        ↓
Policy (normalize / validate / conflict / accept|reject)
        ↓
Store (canonical rows + provenance fields as available)
        ↓
Resolver (applies_to + priority + budget) → ContextBuilder
```

Catalog 示例（starter，design 定稿）：

```yaml
visual.style:
  type: enum
  values: [pixel_art, anime, realistic, minimalist]
  applies_to: [art, plan]
gameplay.difficulty:
  type: enum
  values: [easy, normal, hard]
  applies_to: [plan]
```

---

## 5. 优先拍板问题（改 design 前）

1. 未知 key：**reject/drop**（推荐 P0）还是 staging？
2. 旧数据：映射表 / 归档只读 / 清空——默认选哪个？
3. To-Be 文档：**ADR-16** 还是 ADR-15 amendment？（推荐 ADR-16，保持 As-Is 干净）
4. value 类型：P0 是否强制 enum/bool/number/short-string（拒任意 object）？
5. code/repair：P0 是否 **不注入**（Resolver 空 applies）？
6. evidence 表：P1 是否独立 `preference_evidence`，还是先只在 value 旁挂 message_id？
7. 本单 Close：design-only / Epic 到 P0 落地 / Epic 到 P1？（现行 Issue 按 **Epic 到 P0+核心 P1**）

---

## 6. 自检清单

* [ ] 正文不再把 `(user_id, node, key)` 当作目标唯一键
* [ ] 写明 explicit 不被 cap 静默删除
* [ ] References 指向 ADR-15
* [ ] Verification 与 Priority 表一致
* [ ] Non-goals 含「不做 vector preference 主键」「不做 node-owned 复制行」

---

## 7. 相关文件

| 文件 | 角色 |
| --- | --- |
| [ADR-15](../../adr/ADR-15-preference-memory-as-is.md) | As-Is |
| Issue #162 | To-Be 意图 |
| Issue #124 | Eval 跟随 |
