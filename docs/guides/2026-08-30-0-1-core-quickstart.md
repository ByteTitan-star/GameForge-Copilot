# GameForge 0–1 核心上手指南（赶时间版）

> 目标：最短路径搞清「一次生成怎么跑、挂了怎么办、数据存在哪」。
> 原则：**只抓主干，小细节放过**。本地代码里若看到 `【阅读导读】` 注释，是学习用，勿提交远端。
> 日期：2026-08-30

---

## 0. 90 分钟最小必读（按序）

| 分钟 | 打开 | 只看什么 |
|------|------|----------|
| 0–15 | `backend/app/forge/graph.py` | 文件头；搜 `_build_graph`、`run_generation`、`code_qa_loop_node` |
| 15–35 | `subgraphs/code_qa_loop.py` → `code_qa_exec.py` | 条件边；三个 `execute_*` 返回字段 |
| 35–50 | `sandbox/playtest.py` | `PlaytestResult` 不变量；`run_playtest` |
| 50–65 | `forge/guard.py` | `quick_filter` → `run_streamed_llm_result` → `ContentAttacked` |
| 65–80 | `memory/preferences.py` + `context_builder.py` | 偏好怎么写、怎么注入 |
| 80–90 | 本文 §4–§6 | Redis/MQ/库表/checkpoint；评测口述 |

有余力再翻：`reliability/policy.py`、`hitl.py`、`docs/evals/dashboard.md`。

---

## 1. 产品一句话 + 主链路

**GameForge = 用自然语言生成可试玩小游戏，经策划/美术确认 → 写码 → Playwright 冒烟 → 通过才算可发布。**

```text
用户需求
  → plan（策划）→ HITL 确认
  → art（美术方向）→ HITL 选择
  → CodeQaLoop（code ↔ playtest ↔ diagnose，最多约 3 次 attempt）
  → qa_ok → promote → done
  → 失败 → qa_failed / sandbox_failed（等人）
横切：内容审核 guard；偏好 memory 注入；超时/幂等 reliability
```

**主图节点（8）：** `chat_reply` · `plan` · `revise_plan` · `art_options` · `revise_art_options` · `art_detail` · `code_qa_loop` · `done`
入口路由用 `START` 条件边（`route_start`），不是单独的 `entry_router` 节点。

---

## 2. CodeQaLoop（必须能讲清）

| 点 | 记住 |
|----|------|
| 是什么 | LangGraph **子图**：有界 code/playtest/diagnose |
| 成功标准 | **B 档**：Playwright 可交互冒烟通过 → `qa_ok` |
| 禁止 | 静态 DOM 检查冒充 QA 通过；子图里改 `run.status` / 调 `_fail` |
| 预算 | `code_qa_max_attempts`（默认 3，首次算第 1 次） |
| 通过后 | 主图 `promote_candidate`（candidate → `current_version`） |
| 耗尽后 | `qa_failed`（产品问题）或 `sandbox_failed`（环境/infra） |

**关键文件顺序：**
规格 §1 → `code_qa_loop.py` → `graph.code_qa_loop_node` → `code_qa_exec.py` → `playtest.py` → `code_candidate.py` + `artifact_gate.py`

**口诀：** `previewable ≠ publishable`；`build_ok ≠ qa_ok`；只有 `qa_ok` 才可发布。

---

## 3. 安全护栏（两条线别混）

### A. 内容护栏（生成链路，优先）

```text
用户输入包装(_wrap_user_input)
  → quick_filter（blacklist 正则 + AC 词库）即决
  → 未决则 Guard.audit（审核模型 0/1）
  → 流式输出边生成边滑窗审核
  → 命中 ContentAttacked → run FAILED（不进节点 Retry）
产物侧：cdn_policy 白名单 + CSP（拦任意外站脚本）
```

核心文件：`guard.py` → `blacklist.txt` / `lexicon/` → `config.audit_*` → `cdn_policy.py`

### B. 生产安全基线（选读）

密钥门禁、SSRF（`llm/url_safety.py`）、manifest 黑名单、`dev_routes_enabled` 等 → `ADR-07`。

`knowledge/guards.py` 是 RAG 检索防护，**不是**内容审核。

---

## 4. 用户偏好 / 记忆（三句话）

1. **Explicit**：用户明确长期偏好（「以后/默认…」或 API `PUT /me/preferences`）
2. **Inferred**：弱推断，**不得覆盖**同 `(category,key)` 的 Explicit；active ≤ 50（ADR-02）
3. **注入**：只经 `ContextBuilder`；偏好是 **data**，不是 system instruction

正式写库：`preferences.upsert_preferences_from_text` → `llm_extract`（未配置抽取模型则不写）。
会话摘要 `session_summary` ≠ 长期偏好（挂在 Game 上）。

---

## 5. 基础设施对照（面试四句）

| 组件 | 干什么 | 先看哪 |
|------|--------|--------|
| **Redis** | checkpoint 缓存、幂等键、限流、控制信号 | `core/redis.py`、`forge/state.py`、`idempotency.py` |
| **RabbitMQ** | 异步任务：`execute_run` / `resume_run` | `messaging/worker.py`、`forge/queue.py`、ADR-08 |
| **Postgres** | 用户/游戏/run/消息/偏好/**checkpoint 权威** | `models/*`、`run_checkpoints` |
| **S3/本地** | 游戏产物、知识原文 | `hosting/store.py`、`knowledge/source_store.py` |
| **Pinecone** | **两套**：语义缓存 vs 知识库检索 | `cache/pinecone_store.py` vs `knowledge/pinecone_store.py` |
| **Daytona** | 云沙箱（可回退 docker→local） | `sandbox/daytona.py`、`sandbox/__init__.py`、ADR-03 |

**Redis ≠ 消息队列。** API 入队 → Rabbit → worker → `run_generation`。

---

## 6. 数据库与 Checkpoint（已对照本机库）

### 6.1 核心表（按业务）

- **账号**：`users`、`oauth_accounts`、`user_llm_config`、`user_preferences`
- **游戏**：`games`、`game_versions`、`forge_messages`
- **生成**：`generation_runs`、`run_checkpoints`、`run_commands`、`artifact_revisions`、`failure_reports`
- **其它**：`task_outbox`、`publish_requests`、`audit_logs`、`notifications`、`system_settings`

### 6.2 Checkpoint 存在哪

```text
权威：PostgreSQL.run_checkpoints（state JSON + revision）
缓存：Redis  run:ckpt:{run_id}  → {"revision", "state"}
大 payload：artifact_revisions（checkpoint 只留 active_*_revision_id）
```

实现：`forge/state.py` + `checkpoint_slim.py`。

### 6.3 真实样例（本机曾查到）

**plan_confirm（瘦）：** `phase` / `pause_reason=waiting_user` / `active_plan_revision_id`

**qa_failed：** `attempt=3`、`failure_kind=product`、`playtest_errors`、`previewable=true`、`publishable=false`、各 `active_*_revision_id`、`failure_report_id`

自查：

```bash
docker compose up -d postgres redis
docker exec -it 9autogame-postgres-1 psql -U gameforge -d gameforge \
  -c "SELECT run_id, revision, jsonb_pretty(state::jsonb) FROM run_checkpoints;"
```

---

## 7. 评测（面试 40 秒口述）

我们做了 **8 维可复现评测**（`eval/runners/*` → `docs/evals/`，看板 `dashboard.md`）：

| 维度 | 测什么 |
|------|--------|
| Generation / Code Quality | 端到端能否成功、产物质量 |
| Security / Output Audit | 对抗注入；输出快筛 |
| Preference | 偏好持久化规则 |
| Reliability / Performance | 故障机制、并发时延 |
| Model Comparison | 模型对比 |

**答法要点：**
「分层评测 + 明确测的是快筛还是 LLM 审核；离线门禁保底 + 抽样 live；有 target，不虚报全量线上 100%。」
RAG 增益评测属 ADR-14，与这 8 维产品评测分开说。

---

## 8. 超时 / 失败（够用就行）

- 节点预算表：`reliability/policy.py`（`code_qa_loop` 外墙 = attempts × 三节点）
- 可恢复 → pause + recovery；Fatal / `ContentAttacked` / 取消 → 终态
- HITL phase 词表：`hitl.py`（`plan_confirm` / `art_confirm` / `qa_failed` / `sandbox_failed`）

---

## 9. 面试高频三问速答

**Q: LangGraph 怎么编排？**
主图 plan→art→CodeQaLoop→done；子图有界闭环；HITL 用 checkpoint 暂停恢复。

**Q: 怎么保证生成质量？**
Playwright B 档硬门禁；未通过不 promote；失败进 HITL 可修可重试。

**Q: 状态存在哪、崩溃会丢吗？**
进度权威在 Postgres `run_checkpoints`；Redis 热缓存；大文档在 `artifact_revisions`；MQ 投递异步执行。

---

## 10. 刻意不先看（省时间）

- ADR-13 原生引擎全文、ADR-14 全文细节
- 前端页面、admin 细配置
- Build Vite 内环每一行、Godot 平行管线
- 学习用中文注释的提交（本地看即可，勿推进 PR）

---

**学完自检：** 能否不看稿画出主图+CodeQaLoop？能否说出 `qa_ok` / promote / checkpoint 三处落点？能否区分 Redis 与 Rabbit、两套 Pinecone？能则 0–1 过线。
