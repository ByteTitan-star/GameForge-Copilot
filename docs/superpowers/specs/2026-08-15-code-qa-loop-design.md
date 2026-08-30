# CodeQaLoop：可交互冒烟硬门禁设计

> **【3 小时上手 · 第 0 步 · 约 20min · 先读本文再碰代码】**
> 读法：只抓 §1 目标 + 已锁定决策表 + Attempt 定义；细节章节有空再翻。
> 读完立刻去：`backend/app/forge/subgraphs/code_qa_loop.py`（第 1 步）。
> 完整顺序见该文件顶部「3 小时上手 · CodeQaLoop 阅读顺序」。

* 日期：2026-08-15
* 状态：已钉死歧义，待实现（实现计划见 `docs/superpowers/plans/2026-08-15-code-qa-loop.md`）
* 关联代码：`backend/app/forge/graph.py`、`backend/app/sandbox/playtest.py`、`backend/app/forge/build/`、`backend/app/core/config.py`

## 1. 目标

用户等到生成 `done` 时，当前候选产物必须至少通过 **可交互冒烟（B 档）**；否则进入 `qa_failed` HITL，禁止通过静态 DOM / 源码检查冒充运行时 QA 成功。

使用 LangGraph **子图** `CodeQaLoop` 将 **code ↔ playtest ↔ diagnose ↔ repair** 收敛为一个有界闭环。整个 CodeQaLoop 最多执行 **3 个 code/QA attempt**，首次生成计为第 1 个 attempt。

不引入新的 Agent 框架；不自研开放式 tool-use loop。

### 已锁定决策

| 项        | 选择                                                |
| -------- | ------------------------------------------------- |
| 成功标准     | B：加载无错 + 注入输入不崩 + 「在动」弱信号                         |
| 门禁       | A：Playwright + Chromium 硬门禁，不可用即 fail             |
| 总预算      | `code_qa_max_attempts=3`，首次生成计第 1 次               |
| 构建内环     | `BUILD_MAX_RETRIES` 保留，仅表示单个 attempt 内的 Vite 构建修复 |
| 编排       | LangGraph 子图                                      |
| 循环单元     | code 与 test/QA 同属一个 loop                          |
| infra 错误 | 消耗 attempt，但不修改用户源码                               |
| 失败终点     | 3 个 attempt 耗尽 → `qa_failed` HITL                 |
| 静态检测     | 不得作为生产 QA 通过路径                                    |

### Attempt 定义

```text
attempt 1:
  generate → build → playtest

attempt 2:
  diagnose → repair → build → playtest

attempt 3:
  diagnose → repair → build → playtest

仍失败:
  exhausted → qa_failed
```

这里的 `3` 表示**总 attempt 数**，不是「初次执行 + 3 次 retry」。

### 非目标

* 玩法级可玩验证，如得分、胜负、关卡推进等 C 档语义
* 新增 Agent 框架或开放 ReAct harness
* 为本地逃逸新增 `playtest_allow_static` 等软开关
* 静态 DOM / 源码检测作为生产 QA 通过路径
* 自动理解具体游戏玩法并生成专用测试脚本

---

## 2. 现状与问题

| 事实                                           | 来源                                        |
| -------------------------------------------- | ----------------------------------------- |
| 主图已有隐式 `code ↔ qa` 回边与诊断修复                   | `graph.py`                                |
| `code_node` 自己还有 `code_max_retries` 外层重试     | `graph.py` / `config.py`                  |
| 默认可以走静态 playtest，JS 未执行也可能 `ok`              | `playtest.py` + `PLAYTEST_USE_PLAYWRIGHT` |
| single-html Playwright 异常后会退回静态结果            | `playtest.py`                             |
| `qa_max_retries` 默认 2，与「最多 3 attempt」不一致     | `config.py`                               |
| `code_max_retries` 与 `qa_max_retries` 两套预算并存 | `config.py` / `graph.py`                  |
| Vite 构建已有独立 `run_project_build_loop`         | `build/integration.py`                    |

当前 single-html fallback 还存在状态不一致风险：

```text
static result:
  ok = true

之后插入:
  errors = ["Playwright 失败..."]

可能最终得到:
  ok = true
  errors != []
```

因此问题不只是「默认是否启用 Playwright」，而是：

1. **生产 QA 成功判定并不强制执行 JS**
2. **Playwright 不可用时存在静态降级**
3. **`ok` 与 `errors` 可产生不一致状态**
4. **code/build/QA 有多层独立 retry，预算语义不清**
5. **主图承担过多 code ↔ QA 细节**
6. **QA 默认从 `current_version` 取产物，无法表达“本 attempt 是否真的生成了新 candidate”**

目标是把这些行为统一成一个显式、有界、不可静默绕过的 CodeQaLoop。

---

## 3. 架构

```text
主图
  plan
    ↓
  HITL
    ↓
   art
    ↓
  HITL
    ↓
  code_qa_loop（子图）
       ├─ ok ─────────→ done
       └─ exhausted ──→ qa_failed HITL
```

CodeQaLoop：

```text
START
  ↓
code_or_repair
  │
  ├─ candidate_ready ──→ playtest
  │                        │
  │                        ├─ pass ──────────────→ END(ok)
  │                        │
  │                        ├─ product fail
  │                        │     → diagnose →（未耗尽）code_or_repair
  │                        │                 （耗尽）END(exhausted)
  │                        │
  │                        └─ infra fail
  │                              → 不 diagnose / 不 repair / 不改源码
  │                              → attempt += 1
  │                              →（未耗尽）直接回 playtest（同一 candidate）
  │                              →（耗尽）END(exhausted)
  │
  └─ build fail
        → diagnose →（未耗尽）code_or_repair
                    （耗尽）END(exhausted)
```

**infra 回边硬约束（钉死）：**

* `failure_kind=infra` 时，条件边**只允许**指向 `playtest`（或等价的「跳过 code_or_repair、保持 `candidate_version` 不变再测」）。
* **禁止**进入 `diagnose` / `repair` / 任何 LLM 修码路径。
* **禁止**与 product/build 的「未耗尽 → code_or_repair」回边混用同一条边。

### 3.1 模块边界

| 单元                                | 职责                                           | 不负责                |
| --------------------------------- | -------------------------------------------- | ------------------ |
| `forge/subgraphs/code_qa_loop.py` | 子图编排、attempt、停机、failure routing、对外结果         | 策划/美术 HITL、引擎选型    |
| `sandbox/playtest.py`             | 单次 B 档 Playwright QA；环境不可用返回明确 fail          | 调 LLM、修源码、控制 retry |
| code/repair service 模块            | generate / repair / build / candidate commit | LangGraph 路由       |
| diagnose helper                   | `QA_PROMPT` + 结构化 fallback diagnosis         | 修改源码               |
| `graph.py`                        | 挂载子图；处理 ok → done / exhausted → qa_failed    | 内嵌多轮 code ↔ qa     |
| `build/integration.py`            | Vite 单次 attempt 内的 build repair 内环           | 消耗 CodeQa attempt  |
| 现有 prompts                        | 尽量复用                                         | 新建第二套 Agent 系统     |

### 3.2 依赖方向

`code_qa_loop.py` 不应 import `graph.py` 的私有内部函数。

现有 `graph.py` 中与 code/QA 相关的业务逻辑应逐步抽到独立 service/helper，例如：

```text
forge/code_generation.py
forge/code_repair.py
forge/qa/diagnose.py
forge/subgraphs/code_qa_loop.py
```

具体路径可按仓库现有风格调整，但要求：

* subgraph 为独立模块
* 业务执行逻辑不能因抽 subgraph 而形成 `graph.py ↔ subgraph.py` 循环依赖
* `graph.py` 只保留主图级 orchestration

### 3.3 子图节点

推荐使用三个逻辑节点。

#### `code_or_repair`

根据 attempt 决定行为：

```text
attempt == 1
  → generate

attempt > 1
  → repair
```

然后：

1. 生成/修复源码
2. 对 Vite 工程执行现有 build loop
3. 成功后写入新的 candidate
4. 返回 `candidate_ready=true`
5. 失败则记录 build failure，不得拿旧产物进入 playtest

#### `playtest`

只测试**当前 attempt 成功产生的 candidate**。

执行 §4 B 档 Playwright 硬门禁，并返回：

* `qa_ok`
* `playtest_errors`
* `console_logs`
* `failure_kind`
* `motion_signal`
* thumbnail

#### `diagnose`

仅处理可修复错误：

```text
product
build
```

输入已有运行时证据：

* errors
* console
* build logs
* 当前源码
* design doc

调用 `QA_PROMPT` 或现有 repair prompts。

LLM 调用失败时，生成结构化 fallback diagnosis。

`infra` 错误不得进入源码 diagnose/repair。

### 3.4 子图状态

新增/保留字段：

```text
attempt: int
qa_ok: bool
exhausted: bool

candidate_version: int | None
candidate_ready: bool
candidate_kind: "single-html" | "project" | None

playtest_errors: list[str]
console_logs: list[str]

failure_kind:
  "product"
  | "build"
  | "infra"
  | None

qa_diagnosis: str

motion_signal:
  "raf"
  | "canvas_diff"
  | "engine_runtime"
  | None

thumbnail_saved: bool
```

继续与主图共享：

```text
design_doc
artifacts
art_direction
paused
failed/cancel state
```

### 3.5 Candidate 不变量

CodeQaLoop 不得默认 QA `game.current_version`。

必须显式追踪：

```text
candidate_version
candidate_ready
```

只有当前 attempt：

```text
candidate_ready == true
```

时才允许进入 playtest。

例如：

```text
attempt 1:
  build v10 success
  playtest v10 fail

attempt 2:
  repair
  build fail
```

此时不得重新测试 v10 并把它视为 attempt 2 的成功产物。

build failure 必须走失败分支。

### 3.5.1 Candidate promote（钉死）

* CodeQaLoop 在 attempt 内写入的版本称为 **candidate**（`candidate_version`），**不得**在 QA 通过前把它当作用户可见的交付版。
* 仅当本轮 playtest `qa_ok=true` 时，主图（或 code/repair service 在子图返回 ok 之后）执行 **promote**：
  * `game.current_version = candidate_version`
  * 托管预览 / 卡片封面指向该版本
  * 此后 `done` 使用该版本
* 失败 attempt 产生的产物可以留盘（便于诊断 / resume 证据），但：
  * 不得更新 `current_version` 为该失败 candidate（除非产品另有「保留上次可玩预览」的既有行为且与本次交付无关）
  * 下一 product/build attempt 必须生成**新的** `candidate_version`，不得把旧失败版伪装成新 candidate 再测通过
* `done` 前置条件见 §14：必须存在已 promote 的通过版本（或等价地 `current_version` 已指向本次 `qa_ok` 的 candidate）。

### 3.6 主图变化

删除主图状态：

```text
qa_retry
```

删除主图：

```text
qa → code
```

隐式回边。

从：

```text
code → qa
qa → code / done
```

改为：

```text
code_qa_loop
  → done
  → qa_failed
```

---

## 4. B 档判定与 Playwright 硬门禁

单次 playtest 必须**全部**满足基础条件，并至少满足一个运行弱信号，才允许：

```text
ok = true
```

### 4.1 Playwright / Chromium 必须可用

任何以下错误都必须：

```text
ok=false
failure_kind=infra
```

例如：

```text
PLAYWRIGHT_UNAVAILABLE
CHROMIUM_UNAVAILABLE
BROWSER_LAUNCH_FAILED
```

禁止：

```text
Playwright fail
→ static fallback
→ ok=true
```

生产 `run_playtest()` / `run_playtest_dist()` 不再读取：

```text
PLAYTEST_USE_PLAYWRIGHT
```

也不得根据环境变量切换成 static mode。

### 4.2 页面加载成功

支持：

#### single-html

将 HTML 写入临时文件后使用 Playwright 加载。

若现有 CSP / 浏览器限制导致 `file://` 行为与生产预览差异明显，也允许统一改为临时 localhost HTTP。

#### Vite / dist

启动临时 localhost HTTP server：

```text
http://127.0.0.1:<port>/
```

必须确认：

* navigation 成功
* 主文档正常返回
* 页面达到可执行状态

不要求等待所有长生命周期网络请求结束。

避免仅依赖 `networkidle`，因为游戏可能长期保留网络或 animation activity。

### 4.3 无未捕获 pageerror

从 navigation 前注册：

```text
page.on("pageerror")
```

整个 QA 窗口内：

```text
pageerror == []
```

包括：

* 首屏初始化
* 输入注入
* click
* motion probe

输入后新增 `pageerror` 同样 fail。

### 4.4 必须注入输入

至少执行：

```text
ArrowRight
Space
```

如果存在可点击按钮，则额外尝试 click 一个**当前可见且 enabled** 的交互元素。

输入注入本身失败：

```text
failure_kind=product
ok=false
```

输入后等待短窗口，再检查新增 pageerror。

本测试不要求输入必须改变游戏语义，只要求页面能够承受基础用户交互而不崩溃。

### 4.5 「在动」弱信号

以下满足任意一项即可。

#### A. 应用 requestAnimationFrame activity

在页面业务 JS 执行前通过 `add_init_script` hook：

```text
window.requestAnimationFrame
```

记录**页面业务代码请求并实际执行的 callback 次数**。

QA 自己不得使用 requestAnimationFrame 作为观察循环，否则会制造自证信号。

测试逻辑使用 Playwright wait / timer：

```text
counter_before
wait short window
counter_after
```

要求：

```text
counter_after > counter_before
```

并达到一个最小 activity 阈值。

#### B. canvas 两帧有可观测变化

存在可见 canvas 时：

```text
frame A screenshot
wait short window
frame B screenshot
```

对 canvas locator 截图做差异比较。

使用最小变化阈值，避免 GPU / antialiasing 微小噪声导致误通过。

不依赖：

```text
canvas.getContext(...).getImageData()
```

作为唯一方案，以避免 WebGL / tainted canvas 限制。

#### C. 已知游戏引擎运行时证据

仅适用于平台已知支持的 renderer：

```text
phaser3
pixijs
...
```

需要证明引擎运行时已经真实挂载，例如：

* renderer canvas 已创建并可见
* 已知引擎 runtime 对象 / renderer 已初始化
* 对应 mount 节点下已有运行时生成的渲染节点

单纯存在：

```html
<div id="game"></div>
```

或：

```html
<div id="app"></div>
```

不得作为 `engine_runtime` 通过依据。

满足 engine runtime 后，仍需：

* 完成输入注入
* 输入后无新增 pageerror

### 4.6 `ok` 不变量

必须保证：

```text
ok == true
⇒ errors == []
⇒ failure_kind is None
⇒ motion_signal != None
```

禁止出现：

```text
ok=true
errors=["..."]
```

推荐：

* `ok` 在函数最终出口统一派生
* 或使用构造 helper
* 不在多个分支独立修改 `result.ok`

### 4.7 封面截图

只有 QA 已通过后才尝试截图。

截图失败：

```text
log warning
thumbnail=None
```

不改变：

```text
qa_ok=true
```

thumbnail 建议当场落盘，不把 PNG bytes 写入 LangGraph checkpoint state。

### 4.8 静态检测

现有 `_static_playtest()` 等逻辑可：

* 删除
* 或保留为单测/helper/CLI diagnostics

但必须满足：

> 生产 CodeQaLoop 无任何路径能够根据 static result 设置 `qa_ok=true`。

---

## 5. Failure 分类与错误处理

### 5.1 Failure Kind

#### `product`

页面本身运行失败，例如：

```text
pageerror
输入导致 crash
缺少运行根结构
无任何 motion signal
浏览器运行时 JS 错误
```

行为：

```text
fail
→ diagnose
→ repair
→ 下一 attempt
```

#### `build`

候选源码无法成功构建或 sandbox execute 失败。

行为：

```text
build fail
→ diagnose/repair
→ 下一 CodeQa attempt
```

Vite 内部可先使用 §6 的 build repair loop。

#### `infra`

基础设施问题，例如：

```text
Playwright import fail
Chromium executable missing
browser launch failed
worker browser dependency损坏
```

行为（与 §3 总图一致，钉死）：

```text
当前 attempt fail（failure_kind=infra）
→ 不调用 QA LLM（禁止 diagnose）
→ 不修改源码（禁止 repair）
→ candidate_version / candidate_ready 保持不变
→ attempt 计数 +1
→ 未耗尽：条件边回到 playtest，再测同一 candidate
→ 耗尽：END(exhausted) → 主图 qa_failed
```

这样保持“Playwright 不可用必须 fail”的硬门禁，同时避免 worker 环境问题导致 LLM 反复污染源码。

### 5.2 超时

navigation / interaction / probe timeout：

* 若 browser 正常运行、页面本身卡死 → `product`
* 若明确 browser/runtime 无法启动 → `infra`

### 5.3 diagnosis LLM 失败

不得直接终止 loop。

生成结构化 diagnosis，例如：

```json
{
  "summary": "QA 诊断模型调用失败，依据确定性运行证据继续修复",
  "root_causes": ["..."],
  "required_fixes": [
    {
      "priority": "P0",
      "location": "根据运行时错误定位",
      "change": "修复上述加载/运行/交互错误",
      "expected_result": "B 档冒烟通过"
    }
  ],
  "regression_checks": [
    "页面成功加载",
    "ArrowRight / Space 注入不崩溃",
    "无 pageerror",
    "存在运行弱信号"
  ]
}
```

fallback diagnosis 不再包含：

```text
得分
关卡推进
胜负
重开流程
```

等 C 档要求。

### 5.4 cancel / pause

用户 cancel / pause 优先于 CodeQaLoop 自动重试。

每个可能执行：

* LLM
* build
* Playwright

的长步骤之间继续检查现有 control state。

---

## 6. Vite Build 内环

现有：

```text
run_project_build_loop
BUILD_MAX_RETRIES
```

保持不变。

语义：

> 单个 CodeQa attempt 中，一份 project candidate 最多执行 `BUILD_MAX_RETRIES` 次「构建 → build repair → 重建」。

这不是 CodeQa attempt。

例如：

```text
CodeQa attempt 2
  repair source
    ↓
  Vite build attempt 1
    fail
  Vite build repair
  Vite build attempt 2
    pass
    ↓
  playtest
```

此时：

```text
CodeQa attempt = 2
build_attempt = 2
```

### Vite → single-html fallback

保留现有 Vite build 内环，但**取消自动跨格式降级 single-html 作为默认成功路径**。

即：

```text
Vite build retries exhausted
→ failure_kind=build
→ 返回 CodeQaLoop
→ 下一 CodeQa attempt repair project
```

原因：

* design routing 已明确选择 Vite 时，不应因构建失败悄悄改变交付形态
* 避免 `BUILD_MAX_RETRIES` 后额外再调用一次 full single-html generation，导致预算难以解释
* CodeQaLoop 已经提供统一外层修复预算

如果未来确实需要 Vite → single-html fallback，应单独形成产品决策，而不是继续作为隐藏降级路径。

---

## 7. qa_failed HITL

CodeQaLoop 自身不得：

```text
_fail()
设置 run.status
设置 ended_at
写 fatal ERROR
```

它只返回：

```text
qa_ok=false
exhausted=true
```

由主图统一进入：

```text
qa_failed
```

### 7.1 qa_failed 状态（契约变更，钉死）

**目标语义（本规格）：** 真正 HITL，不是终态 FAILED。

```text
run.status = PAUSED
run.phase = qa_failed
run.ended_at = None
```

checkpoint 保存：

```text
phase=qa_failed
design_doc
candidate_version
playtest_errors
failure_kind
qa_diagnosis
```

并复用现有 HITL `resume_grant` / `hitl/resolve` 机制。

**相对现状的破坏性变更（必须同 PR / 同计划落地）：**

| 层 | 现状 | 本规格 |
|----|------|--------|
| 后端耗尽 | `_fail()` → `FAILED` + `ended_at`，checkpoint 仍写 `qa_failed` | **禁止**子图/主图在耗尽时 `_fail()`；只 `PAUSED` + `phase=qa_failed` |
| 前端 | `resume.ts` 把 `qa_failed` 当 FAILED 终态，不展示可点 HITL 卡，走失败恢复条 + `/retry` | 改为：`status=paused` + `phase=qa_failed` 时展示可 resume 的 HITL/恢复 UI（与 `plan_confirm` 同属 paused 通道，文案区分） |
| API | `/retry` 专供 failed 的 sandbox/qa | 保留 `/retry` 作兼容**或**统一走 `hitl/resolve`；实现计划须二选一并改测试，禁止两套语义并存导致 409 |
| 单测 | `test_runs` / `resume.test.ts` 假定 FAILED | 同步改为 PAUSED HITL 断言 |

不把 `qa_failed` 作为 `FAILED + ended_at` 的终态。用户**主动 cancel** 仍走真正 FAILED（§7.3）。

### 7.2 用户 resume

用户从 `qa_failed` 明确 resume（`hitl/resolve` 或计划选定的唯一恢复 API）后：

```text
子图内 attempt 计数清空
下一次进入 code_or_repair 时 attempt = 1
```

即重新给予完整：

```text
code_qa_max_attempts=3
```

自动预算（共 3 个 attempt，与首次进入子图相同）。

**禁止**写成 `attempt reset → 0` 后又在别处「从 0 再 +1 变成 1」与「从 1 开始」混用——对外与测试一律断言：**resume 后第一轮 `attempt==1`**。

历史失败证据可以继续作为首次 repair 输入，但不得因为 checkpoint 中旧的 `attempt=3` 导致 resume 后立即 exhausted。

### 7.3 cancel

用户主动终止仍走现有真正 FAILED/cancel 语义。

---

## 8. Observability

### 8.1 Langfuse

CodeQaLoop phase：

```text
code_qa
```

至少记录 span：

```text
code
repair
build
playtest
diagnose
```

属性建议包含：

```text
attempt
build_attempt
candidate_version
candidate_kind
failure_kind
motion_signal
```

### 8.2 WebSocket

每次 playtest 均发送：

```text
QA_REPORT
```

payload：

```json
{
  "passed": false,
  "attempt": 2,
  "issues": [],
  "console_logs": [],
  "playtest_mode": "playwright",
  "failure_kind": "product",
  "motion_signal": null
}
```

成功例：

```json
{
  "passed": true,
  "attempt": 2,
  "issues": [],
  "console_logs": [],
  "playtest_mode": "playwright",
  "failure_kind": null,
  "motion_signal": "canvas_diff"
}
```

`playtest_mode` 生产 CodeQaLoop 固定：

```text
playwright
```

不再使用：

```text
sandbox
static
```

表达 QA 类型。

### 8.3 Error Code

建议统一结构化 issue code，例如：

```text
PLAYWRIGHT_UNAVAILABLE
CHROMIUM_UNAVAILABLE
PAGE_LOAD_FAILED
PAGE_ERROR
INPUT_INJECTION_FAILED
NO_RUNTIME_SIGNAL
BUILD_FAILED
```

`issues` 可同时保留面向人的 message。

### 8.4 Token

LLM response usage 继续按现有机制写 Redis / observability。

Playwright / build 不产生 token usage。

---

## 9. 配置与环境变量清理

| 项                             | 动作                    |
| ----------------------------- | --------------------- |
| `PLAYTEST_USE_PLAYWRIGHT`     | **删除**                |
| Playwright fail → static pass | **删除**                |
| `qa_max_retries`              | **删除**                |
| `code_max_retries`            | **删除作为 code/QA 外层预算** |
| `code_qa_max_attempts`        | **新增，默认 3**           |
| `BUILD_MAX_RETRIES`           | **保留**                |
| `THUMBNAIL_ENABLED`           | **保留**                |
| `playtest_allow_static`       | **不新增**               |

若 code generation 确实存在纯格式解析的小重试需求：

* 使用模块内部常量
* 不与 CodeQaLoop attempt 混用
* 不暴露第二套 code QA 环境变量

例如：

```text
CODE_OUTPUT_PARSE_MAX_ATTEMPTS = 2
```

仅用于输出 malformed 等非完整重新生成逻辑。

### 9.1 config 注释同步

`thumbnail_enabled` 不再描述为：

```text
实际依赖 PLAYTEST_USE_PLAYWRIGHT
```

改为：

> QA Worker 必须具备 Playwright + Chromium；QA 通过后若 `THUMBNAIL_ENABLED=true` 则尝试截图。

### 9.2 环境与文档

同步检查并修改：

```text
backend/.env
backend/.env.example
docs/development*.md
docs/reliability.md
forge/skills/playtest.md
CI / Dockerfile / worker image docs
```

删除：

```text
Playwright optional
默认 static
PLAYTEST_USE_PLAYWRIGHT=1 才真实运行
```

统一为：

> 执行生成任务的 Worker 必须安装 Playwright 及对应 Chromium。浏览器运行时 QA 是 `done` 的必要条件。

---

## 10. Worker 环境

既然 Playwright 是硬门禁，部署环境必须把 Chromium 当成运行依赖，而不是 optional tooling。

Worker image / installation 流程必须确保：

```text
python playwright package
compatible Chromium binary
所需 browser system dependencies
```

CI 至少需要一条测试检查：

```text
async_playwright()
chromium.launch()
new_page()
```

能够成功。

若生产 Worker 缺失该环境：

```text
所有 CodeQaLoop 必须 fail
```

不能以 static fallback 保证可用性。

---

## 11. 测试验收

### 11.1 Playtest 单测

覆盖：

1. 页面初始化 `pageerror` → fail
2. 输入前正常、输入后 `pageerror` → fail
3. keyboard injection 抛异常 → fail
4. button click 导致 crash → fail
5. 无任意 motion signal → fail
6. rAF activity → pass
7. canvas frame diff → pass
8. known engine runtime signal → pass
9. 静态 root 存在但无 runtime → 不得仅凭 root pass
10. thumbnail 截图失败 → QA 仍 pass

### 11.2 Playwright 硬门禁

覆盖：

```text
playwright import unavailable
chromium unavailable
browser launch exception
```

全部必须：

```text
ok=false
failure_kind=infra
```

不得调用 `_static_playtest()` 后通过。

### 11.3 Result invariant

增加测试保证永远不存在：

```text
PlaytestResult(
  ok=True,
  errors=[...]
)
```

### 11.4 子图

覆盖：

#### 一轮通过

```text
attempt 1
generate/build success
playtest pass
→ ok
```

#### 修复后通过

```text
attempt 1 fail
diagnose
attempt 2 repair
playtest pass
→ ok
```

#### 三轮耗尽

```text
attempt 1 fail
attempt 2 fail
attempt 3 fail
→ exhausted=true
→ main graph qa_failed
```

不得出现 attempt 4。

### 11.5 Infra failure

```text
candidate build success
Playwright unavailable
```

验证：

* attempt 增长
* repair LLM 调用次数为 0
* candidate_version 不变
* 3 次后 exhausted

### 11.6 Candidate 防旧版本误测

测试：

```text
attempt 1:
  v5 build success
  QA fail

attempt 2:
  build fail
```

验证：

```text
playtest(v5)
```

不能在 attempt 2 被再次调用。

### 11.7 Vite Build

验证：

* `BUILD_MAX_RETRIES` 语义不变
* build retry 不增加 CodeQa attempt
* Vite build 耗尽后返回 `failure_kind=build`
* 不自动转 single-html
* 下一 CodeQa attempt 能基于 project source repair

### 11.8 QA resume

三轮耗尽进入：

```text
run.status=PAUSED
phase=qa_failed
ended_at=None
```

resume 后：

```text
第一轮 code_or_repair / playtest 的 attempt == 1
不得出现 resume 后立刻 exhausted
```

且保留上次 QA 失败证据用于 repair。前端不得再把该态当成 FAILED 死卡。

### 11.9 配置清理

代码库全文检查：

```text
PLAYTEST_USE_PLAYWRIGHT
qa_max_retries
code_max_retries
```

生产路径中不应再存在旧预算或浏览器软开关依赖。

### 11.10 集成测试

有 Chromium 的 CI / integration 环境：

1. 最小 canvas 动画 HTML → pass
2. 最小 Phaser/Pixi page → pass
3. 静态 canvas 不动 → fail
4. runtime throw → fail
5. keyboard throw → fail
6. bad script → repair → pass（LLM mock）
7. Vite dist → localhost HTTP → pass
8. Chromium 不存在 → 明确 fail

---

## 12. 实现约束

* 编排使用 LangGraph 子图
* 不引入 Agent SDK / ReAct harness
* 异步 IO
* 不硬编码密钥
* 单函数倾向 ≤50 行
* browser probe / motion probe / candidate handling 分模块
* 修改公共逻辑同步补 `backend/tests/`
* 不在业务代码硬编码具体游戏玩法规则
* QA prompt 只围绕 B 档运行时证据修复
* `BUILD_MAX_RETRIES` 与 `code_qa_max_attempts` 必须保持不同维度
* 子图不得自行处理主图级 HITL / run finalization
* 不允许静态 fallback 影响生产 `qa_ok`
* 不允许测试非当前 attempt 产生的旧 candidate

---

## 13. 建议实现顺序

### P0：先把 Playtest 变成真正硬门禁

1. 删除 `PLAYTEST_USE_PLAYWRIGHT`
2. 删除生产 static fallback
3. 统一 Playwright unavailable error
4. 修正 `ok/errors` invariant
5. 增加 input-after-pageerror 检查
6. 实现 runtime motion signals
7. 补 playtest 单测

此阶段即使还没子图，也应先确保：

```text
现有 qa_node 不可能静态假通过
```

### P1：抽 Code / QA 业务逻辑

从 `graph.py` 抽出：

```text
generate/repair
build candidate
diagnose
playtest candidate
```

保持现有行为测试通过。

### P2：引入 CodeQaLoop 子图

1. 新增 `code_qa_max_attempts`
2. 增加 attempt / candidate state
3. 接入 code_or_repair
4. 接入 playtest
5. 接入 diagnose
6. 实现 bounded loop

### P3：主图瘦身

删除：

```text
code node
qa node
qa_retry
qa → code
```

改为：

```text
code_qa_loop → done / qa_failed
```

### P4：统一 qa_failed HITL

改为：

```text
PAUSED
phase=qa_failed
ended_at=None
```

恢复统一走 `hitl/resolve`（`/retry` 若保留则内部收敛到同一 resume 路径，禁止 FAILED 才能 retry）。

补 resume 后第一轮 `attempt==1`；同步前端 `resume.ts` 与相关单测（见规格 §7.1）。

### P5：环境与文档清理

最后全文搜索旧环境变量、retry 名称和 static-default 描述，并更新 Worker image / CI。

---

## 14. Done 条件

一个 generation run 只有满足以下条件才允许进入：

```text
phase=done
status=DONE
```

必须存在最近一个 candidate，且：

```text
candidate_ready == true
qa_ok == true
playtest_mode == "playwright"
failure_kind == None
motion_signal != None
playtest_errors == []
```

任何以下情况都不得进入 `done`：

```text
Playwright 不可用
Chromium 不可用
build 未成功产生当前 candidate
存在 pageerror
输入注入失败
无运行弱信号
仅静态 DOM 检测通过
仅源码 lint 通过
旧 candidate 曾经通过但当前 attempt 未产生有效产物
```

最终保证：

> **用户看到 `done`，意味着当前交付版本确实在 Chromium 中加载并运行过，接受过基础输入，未发生未捕获运行时错误，并且出现至少一个运行活动弱信号。**
