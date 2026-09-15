# ADR-18: Native Tool HITL + 取消固定确认门

* Status: **Accepted**
* Date: 2026-09-15
* Owner 决策：HITL 从「图结构固定门 + inline JSON 提问协议」演进为「原生工具绑定 + 自主流水线」；偏好记忆是决策的第一信号源，ask_user 工具只在偏好不覆盖且决策模糊时兜底。
* Supersedes: [ADR-17](./ADR-17-ask-user-tool.md)（inline JSON 工具协议——非生产级做法，被原生工具绑定取代）
* Related: [ADR-10](./ADR-10-checkpoint-hitl-idempotency.md)（checkpoint/resume_grant/idempotency 全套保留复用）、[ADR-16](./ADR-16-preference-memory-to-be.md)（偏好记忆 = "不问"的信号源）

---

## 0. 动机

1. **固定确认门不够灵活**：plan_confirm / art_confirm 对每个 run 无差别暂停，
   即使偏好记忆已能覆盖决策（风格/难度/语言/题材等闭集槽位）。
2. **ADR-17 的 ask_user 不是真工具**：把工具契约拼接进 system prompt、
   让模型以"整个输出是一段特定 JSON"的方式表达调用——依赖提示词纪律、
   无法利用模型的原生工具调用训练、无法多轮回填，不是生产级做法。
3. 核心思想：**首次执行且偏好未覆盖 → 决策模糊时可问；有偏好记忆 → 直接用**。
   偏好是常态，提问是兜底。

## 1. TL;DR

| 主题 | 决策 |
| --- | --- |
| 固定门 | `plan_confirm` / `art_confirm` **不再产生**；词表保留一个发布窗口（LEGACY_PHASES）供存量暂停 run resolve，下版本删除 |
| ask_user | **原生工具绑定**：provider 层支持 OpenAI `tools`/`tool_calls` 与 Anthropic `tool_use`（含流式增量聚合与多轮消息）；工具 schema 见 `forge/tools.py` |
| 工具范围 | plan 节点 + art_options（非并行路径）；code/qa 不绑定（失败恢复有自己的通道） |
| 预算 | `forge_ask_user_max_per_run`（默认 2）保留；**耗尽后不再绑定工具**（模型无法发起，取代旧"合成回答重跑一次再问即失败"） |
| 暂停表示 | 复用 ADR-10 全套：checkpoint `phase=agent_question` + `ask_node`/`agent_question`/`ask_user_count` + `_pause_hitl`（WS `hitl_wait` 载荷形状不变） |
| 回答回流 | 新命令 `RunCommandType.ANSWER_QUESTION`（additive）；resume 以 `assistant(tool_calls)` + `role:"tool"` 消息回填到发起节点重生成；**回答同时回流偏好抽取管道**（闭环：回答沉淀为 explicit 偏好，下次不再问） |
| 美术决策 | 无人值守：自动选 `recommended` 项（`parse_art_options` 已强制恰好一个）；偏好记忆注入生成上下文间接影响推荐 |
| 失败暂停 | `qa_failed` / `sandbox_failed` **保留**——它们是重试耗尽后的故障恢复暂停，不是确认门；ask_user 解决决策模糊，解决不了环境故障 |
| BYOK 降级 | 能力表 `provider.tools_supported`（`llm_tools_blocklist` 模型前缀黑名单）；不支持的模型静默不绑定工具，agent 自主决策，不退回文本协议 |
| 审核联动 | tool_call 参数序列化后过输出审核（问题文本将展示给用户）；命中与正文同等处理（ContentAttacked） |

## 2. 实现要点

### 2.1 provider 层（`app/llm/provider.py`）

- `_build_body` 新增 `messages` / `tools` / `tool_choice`：OpenAI 路径直传；
  Anthropic 原生路径转换（tools → `name/description/input_schema`；
  `role:"tool"` → user `tool_result` block；assistant `tool_calls` → `tool_use` block）。
- 非流式解析读 `message.tool_calls` / `content[type=tool_use]`；流式解析按 index/块
  聚合增量（OpenAI `delta.tool_calls` 分片 / Anthropic `input_json_delta`），末帧发出。
- `LLMCompletion.tool_calls` / `StreamChunk.tool_calls`（OpenAI 规范形态）。
- 未使用工具的调用**完全保持原请求形状**（新 kwargs 仅在显式使用时传递）。

### 2.2 forge 工具层（`app/forge/tools.py`，替代旧 `ask_user.py`）

- `ASK_USER_TOOL_SCHEMA`：description 内置"记忆优先"纪律（MEMORY_DATA 已覆盖维度
  禁止再问；一次一问最多 4 选项；能自决不问）。
- `validate_ask_user_args` / `extract_ask_user_call`：参数校验失败按未调用处理
  （走产物解析路径，不 crash）。
- `ask_messages`：问答回填多轮消息（assistant tool_calls + role:tool 结果）。

### 2.3 图结构（`app/forge/graph.py`）

- `plan → art_options → art_detail → code_qa_loop → done` 连续执行；
  `_llm_with_ask` 是工具循环包装（绑工具 → 检测 tool_calls → 暂停 agent_question）。
- **副作用迁移**（原 `_commit_hitl_side_effects` 在暂停时提交）：
  - `_finish_plan`：标题同步 + `ensure_plan_revision` + 设计消息 + 进度检查点
    （`phase="art"` 供崩溃/手动暂停后续跑路由）；
  - `_finish_art_options`：`ensure_art_options_revision` + 自动选择留痕消息。
- `route_start`：`agent_question` / `ANSWER_QUESTION` 按 checkpoint `ask_node`
  路由回发起节点（存量无 `ask_node` 默认 plan——旧版提问只在 plan）。

### 2.4 偏好闭环（ADR-16 增量）

`_build_answer_messages` 把用户回答送入 `upsert_preferences_from_text`：回答是
最强的 explicit 偏好信号（用户亲口说的），沉淀后同类决策不再提问——"有了偏好
就不用问"的闭环由此成立。

## 3. 迁移（legacy 窗口）

- `HITL_PHASES` 保留 `plan_confirm` / `art_confirm`（`LEGACY_PHASES` 标记，可
  resolve 不再产生）；前端 HitlCard 对应分支保留一个版本。
- 命令 `APPROVE_PLAN` / `SELECT_ART_A/B` / `REVISE_ART` 变为不可达（枚举保留，
  历史 `run_commands` 行不受影响）。
- 下个版本：删除 legacy 相位、命令与 UI 分支。

## 4. Non-goals / Follow-up

**已完成（2026-09-15 第二批）：**
- **偏好抽取异步化**（`forge/memory/async_extract.py`）：抽取从 plan/art 组装
  关键路径移出（原每次组装前同步多一次抽取 LLM 往返，阻塞首字延迟）；
  fire-and-forget 后台任务 + 独立 session + 超时护栏（`preference_extract_timeout_s`）
  + 内容哈希 24h 去重；失败只 log（best-effort，绝不影响 run）。
- **工具运行时降级**：绑定 tools 收到 400（静态能力表覆盖不到的 compat 端点）
  自动去 tools 重试一次（非流式与流式均为，不消耗传输层重试预算），行为降级
  为无工具调用，不把端点能力问题抛给用户。
- **真实端点冒烟脚本** `scripts/tools-smoke.py`：验证端点接受 tools 字段 +
  模型发起 ask_user + 流式聚合（配 `SMOKE_*` 环境变量运行；单测全为
  MockTransport，上线前用真实 BYOK key 跑一次）。
- **chat_reply 不绑 ask_user（决策）**：问答场景模型可直接以自然语言反问，
  HITL 暂停机制服务于生成流水线，聊天里引入暂停反而打断对话。

**已完成（2026-09-15 第三批·偏好策略增量）：**
- **explicit 时间衰减 / 复确认**：超过 180 天未复确认（`updated_at` 陈旧，非
  `last_used_at`——后者每次注入都刷新，"被使用"≠"被复确认"）的 explicit 可被
  ≥0.85 置信的 inferred 覆盖，note 留审计痕；`preference_explicit_stale_days<=0`
  关闭回到绝对恒胜。
- **scope 防污染**：抽取规则区分"这个游戏/本作"限定的单游戏要求（非偏好）
  与跨游戏普遍口味；game 级结构化存储仍为开放项（当前靠会话摘要承担）。
- **行为信号 inferred**：异步抽取任务携带近期需求历史（默认 8 条），
  同一倾向 ≥2 次复现才可低置信 inferred——取代已消失的"用户选 A/B"信号。
- **worker 优雅关停 drain**：`_consume` 关停块限时（10s）等待在途抽取任务。

**仍开放（按优先级）：**
1. game 级偏好的结构化存储（scope 列 + 按游戏解析；当前靠抽取防护 + 会话摘要）
2. 美术单方向直接生成（省一次选项生成调用）
3. 并行美术路径的提问能力（当前并行模式不绑工具——产品决策：偏好目录
   visual.* 恰好全覆盖美术维度，靠偏好 + recommended 自主决策即可）
4. legacy 相位 / 命令 / UI 分支的最终删除（下个版本）

## 5. 验收证据

- 后端：`pytest tests/` 973+ passed（含 `test_provider_tools.py` 双协议工具解析 +
  运行时 400 降级 12 例、`test_async_extract.py` 异步抽取 4 例、
  `test_ask_user*.py` 工具协议重写、全流程自主跑通
  `test_full_generation_autonomous_flow`）。
- 前端：`pnpm vitest run` 156 passed；`tsc --noEmit` 通过。
- 契约：openapi 无形状变化（命令类型为自由字符串），`test_openapi` 通过。
- 真实端点冒烟：`scripts/tools-smoke.py` 就绪（配 `SMOKE_PROVIDER/MODEL/
  APIKEY/BASE_URL` 运行；仓库内无 key，上线前执行）。
