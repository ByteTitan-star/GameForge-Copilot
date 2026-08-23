# CodeQaLoop 可交互冒烟硬门禁 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 用 LangGraph 子图 `CodeQaLoop` 把 code↔playtest↔diagnose↔repair 收成最多 3 个 attempt 的有界闭环；生产 QA 强制 Playwright 可交互冒烟；`done` 仅在当前 candidate 真跑通过后成立。

**架构：** 先加固 `sandbox/playtest.py` 硬门禁与 B 档信号（P0），再从 `graph.py` 抽出 generate/repair/diagnose/candidate 服务（P1），引入 `forge/subgraphs/code_qa_loop.py`（P2），主图改为挂载子图（P3），将 `qa_failed` 改为真正 `PAUSED` HITL 并同步前端（P4），最后清环境变量与文档/Worker（P5）。规格：`docs/superpowers/specs/2026-08-15-code-qa-loop-design.md`。

**技术栈：** Python 3.12、LangGraph、Playwright async API、FastAPI、pytest、现有 Redis checkpoint / WS / Langfuse。

**钉死决策（实现不得偏离）：**

1. `infra` 失败：只回 `playtest`，禁止 diagnose/repair；attempt+1；同 `candidate_version`。
2. 仅 `qa_ok=true` 时 promote `candidate_version` → `game.current_version`。
3. `qa_failed`：`status=PAUSED`，`ended_at=None`；恢复统一走 HITL（`hitl/resolve`）；resume 后下一轮 `attempt==1`。
4. 删除 `PLAYTEST_USE_PLAYWRIGHT`、生产 static 假通过、`qa_max_retries`/`code_max_retries` 外层预算；新增 `code_qa_max_attempts=3`。
5. Vite 构建耗尽后 `failure_kind=build`，**不**自动降级 single-html。

---

## 文件结构（将创建 / 修改）

| 文件 | 职责 |
|------|------|
| `backend/app/sandbox/playtest.py` | 单次 B 档 Playwright；`failure_kind`；无 static 生产通过 |
| `backend/app/sandbox/motion.py`（新建） | rAF / canvas_diff / engine_runtime 探针 |
| `backend/app/forge/subgraphs/__init__.py`（新建） | 包导出 |
| `backend/app/forge/subgraphs/code_qa_loop.py`（新建） | LangGraph 子图编排 |
| `backend/app/forge/code_candidate.py`（新建） | generate/repair 落盘、candidate 版本、promote |
| `backend/app/forge/qa/diagnose.py`（新建） | QA 诊断 + fallback JSON |
| `backend/app/forge/graph.py` | 挂载子图；删隐式 code↔qa；qa_failed HITL |
| `backend/app/forge/build/integration.py` | 去掉 Vite→single-html 默认成功降级 |
| `backend/app/core/config.py` | `code_qa_max_attempts`；删旧 retry 字段 |
| `backend/app/schemas/ws.py` | `QA_REPORT` 增 `attempt`/`failure_kind`/`motion_signal` |
| `backend/app/api/runs.py` / `games/services.py` | qa_failed 恢复与 `/retry` 收敛 |
| `frontend/src/pages/forge/resume.ts` 等 | paused qa_failed HITL UI |
| `backend/tests/test_playtest*.py`、`test_code_qa_loop.py` 等 | 验收 |
| `docs/development*.md`、`forge/skills/playtest.md`、`.env.example` | 文档与配置清理 |

---

### 任务 1：PlaytestResult 不变量 + 删除生产 static 通过（P0 前半）

**文件：**

- 修改：`backend/app/sandbox/playtest.py`
- 修改：`backend/tests/test_playtest.py`
- 修改：`backend/tests/test_playtest_dist.py`

- [ ] **步骤 1：写失败测试——ok 与 errors 不得同时为真**

```python
# backend/tests/test_playtest.py
import pytest
from app.sandbox.playtest import PlaytestResult

def test_playtest_result_rejects_ok_with_errors() -> None:
    with pytest.raises(ValueError):
        PlaytestResult(ok=True, errors=["x"], console_logs=[])
```

- [ ] **步骤 2：运行确认失败**

```bash
cd backend && uv run pytest tests/test_playtest.py::test_playtest_result_rejects_ok_with_errors -v
```

预期：FAIL（尚无校验）或 import/构造无校验。

- [ ] **步骤 3：实现最少不变量**

在 `PlaytestResult` 使用 `__post_init__`（若为 dataclass）或工厂 `make_playtest_result(errors=..., ...)`：`ok = (not errors) and failure_kind is None and (motion_signal is not None if requiring motion else ...)`。本任务先保证：`ok=True ⇒ errors==[]`。先给 dataclass 增加字段占位：

```python
failure_kind: str | None = None  # "product"|"build"|"infra"
motion_signal: str | None = None  # "raf"|"canvas_diff"|"engine_runtime"
```

生产路径：`run_playtest` / `run_playtest_dist` **删除**对 `PLAYTEST_USE_PLAYWRIGHT` 的读取；Playwright 不可用时返回 `ok=False, failure_kind="infra", errors=[...]`，**禁止**调用 `_static_playtest` 后设 `ok=True`。

- [ ] **步骤 4：改旧「无 Playwright 则静态通过」测试**

将依赖 static pass 的用例改为：

- 显式测 `_static_playtest` helper（若保留）仅作诊断；或
- 断言无 Playwright 时 `ok is False` 且 `failure_kind == "infra"`。

- [ ] **步骤 5：跑相关测试并 commit**

```bash
cd backend && uv run pytest tests/test_playtest.py tests/test_playtest_dist.py -v
git add backend/app/sandbox/playtest.py backend/tests/test_playtest.py backend/tests/test_playtest_dist.py
git commit -m "fix(playtest): 强制 Playwright 失败语义并保证 ok/errors 不变量"
```

---

### 任务 2：B 档输入后 pageerror + motion 探针（P0 后半）

**文件：**

- 创建：`backend/app/sandbox/motion.py`
- 修改：`backend/app/sandbox/playtest.py`
- 测试：`backend/tests/test_playtest.py`、`backend/tests/test_motion.py`（新建）

- [ ] **步骤 1：写 motion 探针失败/成功测试（可 mock page）**

覆盖规格 §11.1 中与探针相关的断言接口，例如：

```python
# backend/tests/test_motion.py
import pytest
from app.sandbox.motion import evaluate_motion_signal

@pytest.mark.asyncio
async def test_engine_root_alone_is_not_motion() -> None:
    # fake page：仅有 #game 空节点，无 runtime
    signal = await evaluate_motion_signal(fake_page_empty_root)
    assert signal is None
```

（实现时用 Playwright mock 或轻量协议对象；不要依赖真实浏览器跑全套 CI，真实浏览器用例标 `@pytest.mark.integration`。）

- [ ] **步骤 2：在 `_playwright_playtest*` 中接入**

顺序钉死：

1. `page.on("pageerror")` 在 goto 前注册
2. goto（避免只靠 `networkidle`；用 `domcontentloaded` + 短 wait）
3. 注入 ArrowRight、Space；可见 enabled 按钮则 click
4. 再检查新增 pageerror → `failure_kind=product`
5. `evaluate_motion_signal`；全无 → `NO_RUNTIME_SIGNAL` / product
6. 仅 `ok` 派生后且 `thumbnail_enabled` 时截图

- [ ] **步骤 3：跑测 + commit**

```bash
cd backend && uv run pytest tests/test_motion.py tests/test_playtest.py -v
git add backend/app/sandbox/motion.py backend/app/sandbox/playtest.py backend/tests/
git commit -m "feat(playtest): B 档交互冒烟与运行弱信号硬门禁"
```

---

### 任务 3：配置项切换为 `code_qa_max_attempts`（P0/P2 前置）

**文件：**

- 修改：`backend/app/core/config.py`
- 修改：所有引用 `qa_max_retries` / `code_max_retries` 的测试与 `graph.py`（本任务可先改 config + 测试 monkeypatch 名；graph 大改放到任务 6–7）

- [ ] **步骤 1：config 增加并删除**

```python
code_qa_max_attempts: int = 3  # CodeQaLoop 总 attempt（含首次 generate）
# 删除：qa_max_retries、code_max_retries（或先 deprecate 并在任务 7 删引用）
```

格式解析小重试用模块常量，例如在 `code_candidate.py`：

```python
CODE_OUTPUT_PARSE_MAX_ATTEMPTS = 2
```

- [ ] **步骤 2：全文搜索并列出待改引用，本任务至少让 settings 可导入**

```bash
cd backend && rg "qa_max_retries|code_max_retries|PLAYTEST_USE_PLAYWRIGHT" -n
```

- [ ] **步骤 3：commit**

```bash
git add backend/app/core/config.py
git commit -m "refactor(config): 引入 code_qa_max_attempts 替换双预算"
```

（若一步删字段导致全红，允许本任务保留旧字段为 property 别名并在任务 7 删除。）

---

### 任务 4：抽出 diagnose + candidate 服务（P1）

**文件：**

- 创建：`backend/app/forge/qa/__init__.py`、`backend/app/forge/qa/diagnose.py`
- 创建：`backend/app/forge/code_candidate.py`
- 修改：`backend/app/forge/graph.py`（临时改为调用新函数，行为不变）
- 测试：`backend/tests/test_qa_diagnose.py`、`backend/tests/test_code_candidate.py`

- [ ] **步骤 1：迁移 `QA_PROMPT` 诊断调用到 `diagnose.py`**

```python
async def diagnose_playtest_failure(*, ctx, design_doc, errors, console_logs, source_excerpt) -> str:
    ...
    # LLM 失败 → 规格 §5.3 结构化 JSON（无 C 档文案）
```

- [ ] **步骤 2：`code_candidate.py` 提供**

```python
async def generate_candidate(...) -> CandidateResult  # candidate_version, ready, kind, build errors
async def repair_candidate(...) -> CandidateResult
async def promote_candidate(game, candidate_version) -> None  # 仅 qa_ok 后调用
```

不变量：`candidate_ready=False`（build fail）时不得被 playtest 调用。

- [ ] **步骤 3：单测 candidate 防旧版误测（逻辑级）**

```python
async def test_build_fail_does_not_keep_ready_flag():
    ...
    assert result.candidate_ready is False
```

- [ ] **步骤 4：跑现有 forge 相关测试保持绿 + commit**

```bash
cd backend && uv run pytest tests/test_runs.py tests/test_retry_run.py -v
git add backend/app/forge/qa backend/app/forge/code_candidate.py backend/app/forge/graph.py backend/tests/
git commit -m "refactor(forge): 抽出 diagnose 与 candidate 服务供 CodeQaLoop 复用"
```

---

### 任务 5：实现 CodeQaLoop 子图（P2）

**文件：**

- 创建：`backend/app/forge/subgraphs/__init__.py`
- 创建：`backend/app/forge/subgraphs/code_qa_loop.py`
- 测试：`backend/tests/test_code_qa_loop.py`

- [ ] **步骤 1：写子图路由测试（全 mock）**

```python
@pytest.mark.asyncio
async def test_infra_failure_retries_same_candidate_without_repair(monkeypatch):
    # playtest 连续 infra → attempt 到 3 → exhausted
    # assert repair_calls == 0
    # assert candidate_version 不变

@pytest.mark.asyncio
async def test_product_fail_diagnose_then_repair_then_pass():
    ...

@pytest.mark.asyncio
async def test_exhausted_after_three_attempts():
    ...
```

- [ ] **步骤 2：实现子图**

节点：`code_or_repair` → `playtest` →（条件）`diagnose` → `code_or_repair` 或 END。

条件边伪代码：

```python
def after_playtest(state):
    if state["qa_ok"]:
        return "ok"
    if state["attempt"] >= settings.code_qa_max_attempts:
        return "exhausted"
    if state["failure_kind"] == "infra":
        return "replay"  # → playtest only
    return "diagnose"  # → diagnose → code_or_repair
```

子图**禁止**调用 `_fail()` / 写 `run.status`。

- [ ] **步骤 3：WS `QA_REPORT` 每轮带齐字段**

扩展 `backend/app/schemas/ws.py`：

```python
attempt: int
failure_kind: str | None = None
motion_signal: str | None = None
playtest_mode: str = "playwright"
```

- [ ] **步骤 4：测试绿 + commit**

```bash
cd backend && uv run pytest tests/test_code_qa_loop.py -v
git add backend/app/forge/subgraphs backend/app/schemas/ws.py backend/tests/test_code_qa_loop.py
git commit -m "feat(forge): 新增 CodeQaLoop LangGraph 子图"
```

---

### 任务 6：去掉 Vite→single-html 默认降级（规格 §6）

**文件：**

- 修改：`backend/app/forge/build/integration.py`（若 fallback 在此）
- 修改：`backend/app/forge/graph.py` / `code_candidate.py` 中 fallback 分支
- 测试：构建相关测试改为期望 `failure_kind=build` / `fallback_required` 不再触发单 HTML 成功路径

- [ ] **步骤 1：定位并删除「构建耗尽后自动 generate single-html 且视为成功」路径**

`graph.py` 中 `loop_result.fallback_required` → single-html 的成功交付改为：返回 build fail 给 CodeQaLoop。

- [ ] **步骤 2：补测试 + commit**

```bash
cd backend && uv run pytest tests/test_build_pipeline.py -v
git commit -m "fix(build): Vite 构建耗尽不再自动降级 single-html"
```

---

### 任务 7：主图挂载子图并删除 code↔qa 隐式环（P3）

**文件：**

- 修改：`backend/app/forge/graph.py`
- 修改：`backend/tests/test_runs.py`、`conftest.py`（mock 改为 mock 子图或 playtest）

- [ ] **步骤 1：主图边改为**

```text
art_confirm 之后 → code_qa_loop → done | qa_failed_handler
```

删除主图 `qa_retry`、`qa → code`。

- [ ] **步骤 2：ok 时 promote**

子图返回 `qa_ok` 后：

```python
await promote_candidate(ctx.game, state["candidate_version"])
```

再进 `done_node`。

- [ ] **步骤 3：跑 forge 回归 + commit**

```bash
cd backend && uv run pytest tests/test_runs.py tests/test_forge*.py -v
git commit -m "refactor(forge): 主图改挂 CodeQaLoop 子图"
```

---

### 任务 8：qa_failed = PAUSED HITL + 前端契约（P4）

**文件：**

- 修改：`backend/app/forge/graph.py`（exhausted 处理：`_pause_hitl` / 等价，**禁止** `_fail`）
- 修改：`backend/app/api/runs.py`、`backend/app/games/services.py`
- 修改：`frontend/src/pages/forge/resume.ts`、对应组件与 `resume.test.ts`
- 测试：`backend/tests/test_retry_run.py`、`test_runs.py`

**恢复 API 钉死：** `qa_failed` 统一走现有 `hitl/resolve`（approve/modify）。`POST /retry`：若仍保留，对 `phase=qa_failed` 且已是 `PAUSED` 的请求内部转为与 resolve 相同的 resume_grant 入队；**禁止**再要求 `FAILED` 才能 retry。文档与测试只描述一套语义。

- [ ] **步骤 1：后端测试——耗尽后 PAUSED**

```python
assert run.status == RunStatus.PAUSED.value
assert run.phase == "qa_failed"
assert run.ended_at is None
```

- [ ] **步骤 2：resume 后 attempt==1**

子图入口若 checkpoint 含 `resume_from_qa_failed`，强制 `attempt=0` 状态清除后第一轮代码里设 `attempt=1`。

- [ ] **步骤 3：改前端 `resume.ts`**

删除「qa_failed 是 FAILED 终态故不展示 HITL」逻辑；当 `status==='paused' && phase/node==='qa_failed'` 展示可 resolve 的恢复 UI（文案：试玩未通过，可重试修复）。

- [ ] **步骤 4：前后端测试 + commit**

```bash
cd backend && uv run pytest tests/test_retry_run.py tests/test_runs.py -v
cd frontend && pnpm test -- resume.test.ts
git commit -m "feat(hil): qa_failed 改为 PAUSED HITL 并同步前端恢复"
```

---

### 任务 9：环境变量与文档 / Worker（P5）

**文件：**

- `backend/.env.example`、`backend/.env`（若有 `PLAYTEST_*` 则删）
- `docs/development.md`、`docs/development.zh-CN.md`、`docs/reliability.md`
- `backend/app/forge/skills/playtest.md`
- Worker Dockerfile / compose（确保 `playwright install chromium` + 系统依赖）
- CI：增加 chromium smoke（`async_playwright` launch）或标记必跑 integration

- [ ] **步骤 1：全文清除**

```bash
rg "PLAYTEST_USE_PLAYWRIGHT|qa_max_retries|code_max_retries" -n
```

生产路径与文档不得再出现「可选 Playwright / 默认 static」。

- [ ] **步骤 2：`.env.example` 增加**

```text
CODE_QA_MAX_ATTEMPTS=3
THUMBNAIL_ENABLED=true
```

- [ ] **步骤 3：commit**

```bash
git commit -m "docs: CodeQaLoop 硬门禁环境与 Worker 依赖说明"
```

---

### 任务 10：验收清单（整特性 Definition of Done）

对照规格 §11 / §14，全部勾选后再宣称完成：

- [ ] 无 Playwright → `failure_kind=infra`，从不 `ok=true`
- [ ] B 档：pageerror / 输入后崩 / 无 motion → fail；rAF/canvas/engine → 可 pass
- [ ] 子图 1 轮过 / 修后过 / 3 轮 exhausted
- [ ] infra 三连：repair 调用 0 次，candidate 不变
- [ ] build fail 不 playtest 旧 candidate
- [ ] Vite 耗尽不转 single-html 成功
- [ ] `done` 前已 promote；`QA_REPORT.playtest_mode=="playwright"`
- [ ] `qa_failed` → `PAUSED`；resume 后 `attempt==1`
- [ ] 仓库无 `PLAYTEST_USE_PLAYWRIGHT` 生产依赖

最终验证：

```bash
cd backend && uv run pytest
cd frontend && pnpm test
```

---

## 执行方式建议

实现时用 **subagent-driven-development** 按任务 1→10 顺序推进；每任务结束跑该任务所列 pytest，再 commit。遇规格冲突以 `docs/superpowers/specs/2026-08-15-code-qa-loop-design.md` 钉死条款为准。
