# Eval Strict Live Dimensions 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 按路线 B 补齐 `#116/#117/#118/#124/#125`：先增强 `generation_eval` 遥测（默认 `--limit 10`），再派生质量/性能，再做偏好 live、可靠性故障注入，最后接 `main` live CI。

**架构：** 单一 live 造游戏环负责 HITL/poll + 拉取 `/events`/`/messages`；`code_quality_eval`/`performance_eval` 消费 JSON；`preference_eval`/`reliability_eval` 独立 live；PR 仍只跑 offline/security。

**技术栈：** Python 3.12 / httpx / pytest / GitHub Actions / 现有 Forge API

**规格：** `docs/superpowers/specs/2026-08-21-eval-strict-live-dimensions-design.md`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `eval/runners/telemetry.py` | 纯函数：phase 聚合、QA 指标、错误分类、empty 判定（可单测） |
| `eval/runners/generation_eval.py` | live 结束后 harvest 写入 enriched `per_run`；默认 limit=10 |
| `eval/runners/code_quality_eval.py` | `static_baseline` + `live_derived` |
| `eval/runners/performance_eval.py` | guard + 派生 phases/e2e + 并发 N=1,2,3 + sandbox benchmark |
| `eval/runners/preference_eval.py` | baseline + `live_api` |
| `eval/runners/reliability_eval.py` | unit + `live_fault` |
| `eval/datasets/code_quality_samples.json` | 修正 empty 标注/样本 |
| `eval/datasets/preference_scenarios.json` | 扩 implicit/conflict 字段 |
| `eval/datasets/reliability_faults.json` | 扩故障注入 case |
| `eval/datasets/performance_subset.json` | 固定 10 个 gen id（可选，也可用硬编码） |
| `eval/tests/test_telemetry_helpers.py` | telemetry 纯函数测试 |
| `eval/tests/test_code_quality_live_derived.py` | live_derived 聚合测试 |
| `eval/tests/test_performance_aggregation.py` | 百分位/降级计算测试 |
| `eval/tests/test_preference_scenario_schema.py` | dataset schema 校验 |
| `eval/tests/test_reliability_fault_types.py` | fault type 路由/断言辅助 |
| `.github/workflows/eval.yml` | `main` live `--limit 10` |
| `docs/evals/*` + `dashboard.md` | 报告刷新 |

---

### 任务 1：Telemetry 纯函数（TDD）

**文件：**

- 创建：`eval/runners/telemetry.py`
- 创建：`eval/tests/test_telemetry_helpers.py`

- [ ] **步骤 1：编写失败的测试**

```python
# eval/tests/test_telemetry_helpers.py
from eval.runners.telemetry import (
    aggregate_phases,
    classify_qa_error,
    derive_qa_metrics,
    is_empty_or_trivial_html,
)


def test_aggregate_phases_from_phase_start_events() -> None:
    events = [
        {"type": "phase_start", "ts": "2026-08-21T10:00:00Z", "payload": {"phase": "plan"}},
        {"type": "phase_start", "ts": "2026-08-21T10:00:10Z", "payload": {"phase": "code"}},
        {"type": "phase_start", "ts": "2026-08-21T10:01:40Z", "payload": {"phase": "playtest"}},
        {"type": "done", "ts": "2026-08-21T10:02:00Z", "payload": {}},
    ]
    phases = aggregate_phases(events)
    by_name = {p["name"]: p["duration_s"] for p in phases}
    assert by_name["plan"] == 10.0
    assert by_name["code"] == 90.0
    assert by_name["playtest"] == 20.0


def test_classify_qa_error_keywords() -> None:
    assert classify_qa_error("SyntaxError: unexpected token") == "syntax"
    assert classify_qa_error("TypeError: x is undefined") == "runtime"
    assert classify_qa_error("canvas is blank / screenshot mismatch") == "visual"
    assert classify_qa_error("playtest timed out after 60s") == "timeout"
    assert classify_qa_error("sandbox infra unavailable") == "infra"
    assert classify_qa_error("something odd") == "unknown"


def test_derive_qa_metrics_repair_round() -> None:
    qa = derive_qa_metrics(
        attempts=2,
        first_playtest_ok=False,
        final_playtest_ok=True,
        error_categories=["runtime"],
    )
    assert qa["attempts"] == 2
    assert qa["first_pass"] is False
    assert qa["final_pass"] is True
    assert qa["repair_rounds"] == 1


def test_empty_or_trivial_html() -> None:
    assert is_empty_or_trivial_html("") is True
    assert is_empty_or_trivial_html("<html><body></body></html>") is True
    assert is_empty_or_trivial_html("<html><body><canvas id='g'></canvas><script>boot()</script></body></html>") is False
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd "d:/Z-Desktop/找工作/8大模型开发/实战项目/9AutoGame"
uv run --project backend pytest eval/tests/test_telemetry_helpers.py -v
```

预期：FAIL，`ModuleNotFoundError: eval.runners.telemetry` 或 import 错误。

- [ ] **步骤 3：实现最少代码**

在 `eval/runners/telemetry.py` 实现：

- `aggregate_phases(events: list[dict]) -> list[dict]`：按 `phase_start`（及终态 `done`/`failed`）时间差算 `duration_s`；兼容 `type` 为枚举值字符串（小写/原样都试）。
- `classify_qa_error(text: str) -> str`：关键字映射到规格中的六类。
- `derive_qa_metrics(...)`：`repair_rounds = max(0, attempts - 1)` when not first_pass else 0（若 first_pass 则 0）。
- `is_empty_or_trivial_html(html: str) -> bool`：空、仅壳 html、或无 script/canvas 且极短。

事件字段名以仓库真实 `WSEvent` 为准：实现前读 `backend/app/enums.py` 的 `WSEventType` 与一次真实 `/events` 样例；测试 fixture 用真实 `type` 字符串。

- [ ] **步骤 4：运行测试确认通过**

```bash
uv run --project backend pytest eval/tests/test_telemetry_helpers.py -v
```

预期：PASS。

- [ ] **步骤 5：Commit**

```bash
git add eval/runners/telemetry.py eval/tests/test_telemetry_helpers.py
git commit -m "feat(eval): add telemetry helpers for phase and QA metrics"
```

---

### 任务 2：Enrich `generation_eval` harvest + default limit 10

**文件：**

- 修改：`eval/runners/generation_eval.py`
- 修改：`eval/tests/test_generation_eval_helpers.py`（如需 mock harvest）

- [ ] **步骤 1：把默认 `--limit` 改为 10**

```python
parser.add_argument("--limit", type=int, default=10, help="Live prompt limit")
```

- [ ] **步骤 2：在 `_run_one_case` 终态后 harvest**

伪代码（接入现有 httpx client）：

```python
async def _harvest_run_telemetry(client, *, game_id: str, run_id: str) -> dict:
    events_resp = await client.get(f"/api/v1/runs/{run_id}/events")
    events = events_resp.json().get("data") or [] if events_resp.status_code == 200 else []
    msgs_resp = await client.get(f"/api/v1/games/{game_id}/messages")
    messages = msgs_resp.json().get("data") or [] if msgs_resp.status_code == 200 else []
    game_resp = await client.get(f"/api/v1/games/{game_id}")
    game = game_resp.json().get("data") or {} if game_resp.status_code == 200 else {}
    # map events/messages -> phases, qa, artifact via telemetry.py
    return {"phases": ..., "qa": ..., "artifact": ...}
```

将返回值 merge 进 `_run_one_case` 的 result dict。

- [ ] **步骤 3：补充单元测试（mock 事件列表 → harvest 字段）**

若 harvest 逻辑过厚，抽 `_build_telemetry_from_payloads(events, messages, game, terminal) -> dict` 做纯函数测试。

- [ ] **步骤 4：本地冒烟（可选但推荐）**

```bash
# API+worker 已起时
$env:EVAL_LIVE="1"
$env:EVAL_API_BASE_URL="http://127.0.0.1:8000"
$env:EVAL_ACCESS_TOKEN="<token>"
uv run --project backend python -m eval.runners.generation_eval --live --limit 2
```

检查 JSON `per_run[0]` 含 `phases`/`qa`/`artifact`。

- [ ] **步骤 5：Commit**

```bash
git add eval/runners/generation_eval.py eval/tests/test_generation_eval_helpers.py
git commit -m "feat(eval): harvest phases/qa/artifact in live generation eval"
```

---

### 任务 3：`#116` live_derived + 修 offline empty 样本

**文件：**

- 修改：`eval/runners/code_quality_eval.py`
- 修改：`eval/datasets/code_quality_samples.json`
- 创建：`eval/tests/test_code_quality_live_derived.py`
- 修改：`docs/evals/code-quality-eval-report.md`（跑通后）

- [ ] **步骤 1：写失败测试 — 从 fixture generation JSON 聚合指标**

```python
# eval/tests/test_code_quality_live_derived.py
from eval.runners.code_quality_eval import summarize_live_derived


def test_summarize_live_derived_basic() -> None:
    per_run = [
        {
            "id": "gen-001",
            "success": True,
            "qa": {"attempts": 1, "first_pass": True, "final_pass": True, "repair_rounds": 0, "error_categories": []},
            "artifact": {"empty_or_trivial": False},
        },
        {
            "id": "gen-002",
            "success": True,
            "qa": {"attempts": 2, "first_pass": False, "final_pass": True, "repair_rounds": 1, "error_categories": ["runtime"]},
            "artifact": {"empty_or_trivial": False},
        },
    ]
    s = summarize_live_derived(per_run)
    assert s["playtest_pass_rate"] == 1.0
    assert s["repair_effectiveness"] == 1.0  # 1 repaired / 1 first-fail
    assert s["avg_repair_rounds"] == 0.5
    assert s["empty_output_rate"] == 0.0
    assert s["error_category_distribution"]["runtime"] == 1
```

- [ ] **步骤 2：实现 `summarize_live_derived` + CLI/`EVAL_LIVE` 分支**

- 默认仍跑 `static_baseline`。
- 若存在最新 `eval/reports/*_generation_eval.json` 且含 `qa`，或 `--from-generation PATH`，写入 `live_derived` section 到同一报告。
- 报告不再写假的 “All metrics meet” 当 empty 指标未达标。

- [ ] **步骤 3：修正 `code_quality_samples.json`**

对当前失败 id（`cq-002/003/009/014/016/018`）逐条决定：改 `expected_empty` 或收紧/放宽 `is_empty` 启发式（与任务 1 共用 `is_empty_or_trivial_html` 更佳），直到：

```bash
uv run --project backend python -m eval.runners.code_quality_eval
```

`empty_output_detection_accuracy >= 0.90`。

- [ ] **步骤 4：测试通过并 commit**

```bash
uv run --project backend pytest eval/tests/test_code_quality_live_derived.py eval/tests/test_telemetry_helpers.py -q
git add eval/runners/code_quality_eval.py eval/datasets/code_quality_samples.json eval/tests/test_code_quality_live_derived.py docs/evals/code-quality-eval-report.md
git commit -m "feat(eval): derive QA-loop metrics from generation telemetry (#116)"
```

---

### 任务 4：`#117` phases + concurrency + sandbox

**文件：**

- 修改：`eval/runners/performance_eval.py`
- 创建：`eval/datasets/performance_subset.json`（内容：`{"subset_ids":["gen-001",...,"gen-010"]}`）
- 创建：`eval/tests/test_performance_aggregation.py`

- [ ] **步骤 1：写失败测试 — 降级百分比与吞吐**

```python
from eval.runners.performance_eval import latency_degradation_pct, throughput_per_hour


def test_latency_degradation_pct() -> None:
    assert latency_degradation_pct(p95_n1=100.0, p95_n3=150.0) == 50.0


def test_throughput_per_hour() -> None:
    # 10 successes in 1800s wall => 20 / hour
    assert throughput_per_hour(successes=10, wall_clock_s=1800.0) == 20.0
```

- [ ] **步骤 2：实现聚合函数 + 报告字段**

从 generation JSON 读 `wall_clock_s` 与 `phases`，填 `e2e_p50/p95`、`plan_latency_p50_s`、`code_gen_latency_p50_s`。

- [ ] **步骤 3：并发模式**

新增 `--concurrency-bench`（或 `EVAL_PERF_CONCURRENCY_BENCH=1`）：对 N=1,2,3 调用内部 live runner（复用 `generation_eval._run_live`，`EVAL_CONCURRENCY=N`，subset=10）。记录每档 success_rate、e2e_p95、throughput。**注意费用**：默认文档写清；本地可先 `EVAL_PERF_SUBSET_LIMIT=2` 冒烟。

- [ ] **步骤 4：接入 sandbox benchmark**

```python
from app.sandbox.benchmark import run_benchmark
bench = asyncio.run(run_benchmark(rounds=5))
# map local_dry_run.exec_ms_p95 -> sandbox_exec_p95_ms
```

- [ ] **步骤 5：测试 + commit**

```bash
uv run --project backend pytest eval/tests/test_performance_aggregation.py -q
git add eval/runners/performance_eval.py eval/datasets/performance_subset.json eval/tests/test_performance_aggregation.py docs/evals/performance-eval-report.md
git commit -m "feat(eval): add phase timing, concurrency, and sandbox bench (#117)"
```

---

### 任务 5：`#124` preference dataset + live_api

**文件：**

- 修改：`eval/datasets/preference_scenarios.json`
- 修改：`eval/runners/preference_eval.py`
- 创建：`eval/tests/test_preference_scenario_schema.py`

- [ ] **步骤 1：写 schema 测试**

```python
import json
from pathlib import Path

REQUIRED = {"id", "session2_prompt", "expected_preferences"}


def test_preference_scenarios_min_shape() -> None:
    raw = json.loads(Path("eval/datasets/preference_scenarios.json").read_text(encoding="utf-8"))
    assert len(raw) >= 15
    modes = set()
    for row in raw:
        assert REQUIRED <= set(row)
        mode = row.get("mode", "explicit")
        modes.add(mode)
        if mode == "conflict":
            assert row.get("conflict")
    assert "implicit" in modes and "conflict" in modes
```

- [ ] **步骤 2：扩展 JSON**

至少增加若干 `mode=implicit` 与 `mode=conflict` 条目；为旧条目补 `mode`/`expected_in_context`（可由现有 `expected_in_prompt` 迁移）。

- [ ] **步骤 3：实现 live_api**

标志：`--live` 或 `EVAL_LIVE=1`。

流程：

1. 注册临时用户 + verify 验证码（`/api/v1/dev/verification-code`）+ login。
2. 对 explicit：`POST /api/v1/me/preferences` upsert（或发消息触发 extract——优先 upsert 稳定）。
3. `GET /api/v1/me/preferences` 比对 `expected_db`/`expected_preferences`。
4. conflict：先 inferred upsert，再 newer explicit，断言覆盖。
5. session2：创建 game（可选短 run）；检查 messages/上下文含 `expected_in_context`。
6. relevance：若有产物，关键字命中率计入 `preference_relevance`。

保留 offline `context_builder_baseline` 给 CI。

- [ ] **步骤 4：本地 live 冒烟（≥3 scenarios）+ commit**

```bash
uv run --project backend pytest eval/tests/test_preference_scenario_schema.py -q
git add eval/datasets/preference_scenarios.json eval/runners/preference_eval.py eval/tests/test_preference_scenario_schema.py docs/evals/preference-eval-report.md
git commit -m "feat(eval): live preference persistence API eval (#124)"
```

---

### 任务 6：`#125` reliability fault injection

**文件：**

- 修改：`eval/datasets/reliability_faults.json`
- 修改：`eval/runners/reliability_eval.py`
- 创建：`eval/tests/test_reliability_fault_types.py`

- [ ] **步骤 1：扩展 dataset 类型（保留旧 unit cases）**

新增条目示例：

```json
{
  "id": "rel-011",
  "type": "llm_timeout_then_ok",
  "fail_times": 1,
  "expected_recovery": true
}
```

以及 `mid_run_kill_resume` / `oversized_continuation` / `all_fail_degradation` / `stale_cleanup` 各至少 1 条。

- [ ] **步骤 2：写类型路由测试**

```python
from eval.runners.reliability_eval import is_unit_case, is_live_fault_case

def test_case_routing() -> None:
    assert is_unit_case({"type": "truncation_html"})
    assert is_live_fault_case({"type": "llm_timeout_then_ok"})
```

- [ ] **步骤 3：实现 `live_fault` 模式**

- PR/CI 默认只跑 unit（现有）。
- `--live-fault`：对 live cases 执行注入。
- `llm_timeout_then_ok`：优先用可注入的 LLM test double / 代理失败（查仓库是否已有 provider mock；若无，用 `DEV` 钩子或文档化的 env 开关；禁止把失败做成「假绿」）。
- `mid_run_kill_resume`：脚本化 stop/start worker（Linux CI / 本地文档）；Windows 可 skip 并记 `skipped_platform`。
- 汇总：`timeout_retry_recovery_rate`、`checkpoint_resume_success_rate`、`continuation_success_rate`、`degradation_fallback_triggers`。

- [ ] **步骤 4：unit 回归仍 100% + commit**

```bash
uv run --project backend python -m eval.runners.reliability_eval
uv run --project backend pytest eval/tests/test_reliability_fault_types.py -q
git add eval/datasets/reliability_faults.json eval/runners/reliability_eval.py eval/tests/test_reliability_fault_types.py docs/evals/reliability-eval-report.md
git commit -m "feat(eval): add reliability live fault-injection mode (#125)"
```

---

### 任务 7：`#118` CI main live `--limit 10`

**文件：**

- 修改：`.github/workflows/eval.yml`
- 可选文档：`docs/evals/dashboard.md` notes / `docs/development.zh-CN.md` 一小段 secrets 说明

- [ ] **步骤 1：改 `generation_eval` job（push main）**

在现有 offline 步骤之后增加：

```yaml
      - name: Live generation eval (limit 10)
        env:
          EVAL_LIVE: "1"
          EVAL_API_BASE_URL: ${{ secrets.EVAL_API_BASE_URL }}
          EVAL_ACCESS_TOKEN: ${{ secrets.EVAL_ACCESS_TOKEN }}
          GENERATION_LIVE_SUCCESS_MIN: "0.90"
          PYTHONPATH: .:..
        run: |
          if [ -z "$EVAL_API_BASE_URL" ] || [ -z "$EVAL_ACCESS_TOKEN" ]; then
            echo "EVAL_API_BASE_URL and EVAL_ACCESS_TOKEN secrets are required for main live eval"
            exit 1
          fi
          uv run python -m eval.runners.generation_eval --live --limit 10
          # optional: derive #116/#117 from latest JSON
          uv run python -m eval.runners.code_quality_eval
          uv run python -m eval.runners.performance_eval
```

上传 `eval/reports/*generation*` 与 `docs/evals/generation-eval-report.md` 为 artifact。

- [ ] **步骤 2：PR jobs 不变**（security + offline_eval only）。

- [ ] **步骤 3：workflow_dispatch 可选输入 `run_live_fault`**（默认 false）触发 `#125`。

- [ ] **步骤 4：Commit**

```bash
git add .github/workflows/eval.yml docs/evals/dashboard.md
git commit -m "ci(eval): run live generation --limit 10 on main (#118)"
```

---

### 任务 8：Dashboard、关单、收尾验证

**文件：**

- 修改：`eval/run_all.py`（若需展示 live 字段）
- 修改：`docs/evals/dashboard.md`

- [ ] **步骤 1：跑 offline 全套**

```bash
uv run --project backend python backend/scripts/ci_offline_eval_gate.py
uv run --project backend python -m eval.run_all
```

- [ ] **步骤 2：本地 live（limit 10）一次**（成本高，收尾必做）

确认 generation JSON 可驱动 `#116/#117` 报告。

- [ ] **步骤 3：对各 Issue 英文评论 + close**（证据：报告路径、关键指标）

- [ ] **步骤 4：最终 commit（若有报告 diff）**

```bash
git add docs/evals/
git commit -m "docs(eval): refresh dashboard after strict live dimensions"
```

---

## 规格覆盖自检

| 规格章节 | 对应任务 |
|----------|----------|
| §4 generation telemetry + limit 10 | 任务 1–2 |
| §5 `#116` | 任务 3 |
| §6 `#117` | 任务 4 |
| §7 `#124` | 任务 5 |
| §8 `#125`（unit + live_fault；nightly/dispatch） | 任务 6–7 |
| §9 `#118` | 任务 7 |
| §10 顺序 / §13 AC | 任务 8 |

## 占位符扫描

无 TBD/TODO；平台相关 skip 已写明行为（记 `skipped_platform`，不算假绿）。

---

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-08-21-eval-strict-live-dimensions.md`。

**两种执行方式：**

1. **子代理驱动（推荐）** — 每个任务调度一个新子代理，任务间审查，快速迭代
2. **内联执行** — 在当前会话用 executing-plans 批量执行并设检查点

**选哪种方式？**
