# Langfuse LLM Coverage 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 所有业务 LLM 调用进 Langfuse，generation 按 `kind` 命名，主 run 用 `game_id` 作 session。

**架构：** 扩展 `app.core.langfuse` + 薄封装 `platform_complete`；用户路径继续走 `call_llm`；旁路平台 key 不走配额。

**技术栈：** Python / Langfuse SDK v4 / pytest

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/core/langfuse.py` | `observe_generation(kind)`、`propagate_trace_attrs` |
| `backend/app/forge/tracing.py` | `observe_run` 接 session/user/tags |
| `backend/app/llm/client.py` | `call_llm`/`stream` 透传 `kind` |
| `backend/app/llm/platform_complete.py` | 平台旁路 LLM + 观测 |
| `backend/app/forge/memory/llm_extract.py` | 改走 platform_complete |
| `backend/app/forge/cache/semantic.py` | 改走 platform_complete |
| `backend/app/forge/guard.py` | kind/tags/ids |
| `backend/app/forge/graph.py` | observe_run 传 ids；call_llm 传 kind |
| `backend/tests/llm/test_langfuse_integration.py` | 核心观测测试 |
| `backend/tests/llm/test_platform_complete.py` | 旁路封装测试 |

### 任务 1：langfuse 核心 API（TDD）

**文件：** `backend/app/core/langfuse.py`、`backend/tests/llm/test_langfuse_integration.py`

- [x] 写失败测试：`kind` → name `llm:{kind}`；`propagate_trace_attrs` 无 key 不炸
- [x] 实现 `observe_generation`/`propagate_trace_attrs`
- [x] 测试通过

### 任务 2：platform_complete（TDD）

**文件：** 创建 `backend/app/llm/platform_complete.py`；测试 `test_platform_complete.py`

- [x] 写失败测试：成功写 output/usage；失败标 ERROR
- [x] 实现封装
- [x] 偏好/语义确认改接入

### 任务 3：用户路径 + run session

**文件：** `client.py`、`tracing.py`、`graph.py`、`guard.py`、`code_qa_exec.py`（如需）

- [x] `call_llm`/`stream` 增加 `kind`
- [x] `observe_run` propagate session
- [x] Guard / graph 接线
- [x] 跑相关测试

### 任务 4：验证

- [x] `pytest backend/tests/llm/test_langfuse_integration.py backend/tests/llm/test_platform_complete.py -q`
- [x] 必要时跑 forge memory/cache 相关单测
