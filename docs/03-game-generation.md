# 03 · 游戏生成编排

> 一次"设计游戏"请求如何被 LangGraph 驱动成可运行产物。

## 主状态图

主图编排四个子图，子图之间通过共享状态流转，主图持有检查点。

```
[plan] → [art] → [code] → [qa] → [done]
  │                  │       │
  └─HITL─┘           └─retry─┘──┐
                              回退到 code
```

主状态（`GenerationState`）：

| 字段 | 说明 |
|---|---|
| `game_id` | 关联 game 记录 |
| `user_id` | 创建者，用于取 LLM 配置与用量归属 |
| `requirement` | 用户多轮对话累积的需求 |
| `design_doc` | 策划稿（玩法/界面/关卡/数值） |
| `artifacts` | 美术产出清单与资源引用 |
| `code_version` | 当前代码版本指针 |
| `build_result` | 构建产物地址 + 自测结果 |
| `qa_report` | 质检报告 |
| `phase` | plan/art/code/qa/done |
| `messages` | 跨节点共享的事件流 |

## 子图与角色

每个子图是 LangGraph subgraph，自带节点与受限工具集。

### 策划子图 plan
- 职责：把自然语言需求转成结构化设计稿（玩法、界面、关卡、数值、技术选型）。
- 工具：`web_search`（可选）、`design_lint`（自检策划稿完整性）。
- 输出：`design_doc`。
- HITL：产出策划稿后中断，等用户确认或修改意见，确认后才进 art。

### 美术子图 art
- 职责：按设计稿产出/选取素材（图标、精灵、背景、音效）。
- 工具：`asset_generate`（文生图/简单形状生成）、`asset_pick`（从公共资源库选）。
- 输出：`artifacts`（资源清单与引用路径）。
- 取舍：MVP 优先用资源库 + 简单程序化生成，不强依赖大图模型。

### 代码子图 code
- 职责：在沙箱内生成游戏代码 → 构建 → 自测。
- 工具：`execute_code`（沙箱执行）、`read_file`/`write_file`（沙箱内）、`build`（调构建器）、`run_playtest`（沙箱内启动试玩取日志）。
- 输出：`code_version` + `build_result`。
- 失败回退：构建/自测失败 → 携带错误回到 code 节点重试，重试次数上限后挂起交人。

### 质检子图 qa
- 职责：自动试玩校验（能否启动、核心操作是否生效、有无报错）。
- 工具：`run_playtest`、`assert_check`。
- 输出：`qa_report`（通过/不通过 + 问题清单）。
- 不通过：回退 code 修正；多次不通过则交人。

## 检查点与可恢复

- 主图用 LangGraph checkpointer，状态存 Redis（key 含 `run_id`）。
- 中断：用户可主动暂停；HITL 节点天然中断。
- 恢复：前端按 `run_id` 重连 WS，后端从检查点续跑，不丢上下文。
- 超时：单 run 有总时限，超时挂起交人。

## HITL 节点

| 节点 | 中断方 | 目的 |
|---|---|---|
| 策划稿确认 | 用户 | 确认玩法再生成，避免方向跑偏 |
| 自测失败超限 | 用户 | 携带错误等用户介入修方向 |
| 发布前自检 | 用户/管理员 | 提交发布前最终确认 |

## skill 体系（生成方法论，非玩法约束）

`forge/skills/` 放的是"如何生成游戏"的方法论，不是具体玩法：

- `skills/prompting.md`：各子图 prompt 模板与few-shot。
- `skills/conventions.md`：生成代码的工程约定（单文件入口、无构建依赖或指定构建器、产物结构）。
- `skills/playtest.md`：自测脚本怎么写、怎么取日志。

> 约束是"怎么生成、怎么测"，不是"生成什么玩法"。玩法由需求 + Agent 决定。

## 沙箱 execute_code

- 复用现有 execute_code sandbox 资源分级（CPU/内存/时间）。
- code 子图的 `execute_code`/`write_file`/`build`/`run_playtest` 全部在沙箱内执行。
- 代码子图无网络访问（除可白名单）；构建用预置工具链。
- 产物构建后落 hosting，沙箱随 run 销毁。

## 事件流与可观测

- 每个节点出入、每次工具调用、每次 LLM 调用都发事件到事件总线。
- 事件经 WS 推前端，前端展示实时进度。
- 全部 trace（节点/工具/LLM 调用/prompt/响应）上报 langfuse Cloud（SaaS），供回看与调试；LangGraph 经 langfuse callback 集成自动上报，无需自建 trace 表。
- 配额限流仍走 Redis usage（见 [05-tenant-usage-llm.md](05-tenant-usage-llm.md)），与 langfuse 职责正交。

## 并发与配额

- 单用户同时进行的 generation_run 数量受限。
- 每 run 受用户 token 配额约束（见 [05-tenant-usage-llm.md](05-tenant-usage-llm.md)）。
- 配额耗尽时 run 挂起，提示用户。
