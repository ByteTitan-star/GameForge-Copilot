# QA 试玩约定（Platform Policy · CodeQaLoop · B 档硬门禁）

> 本文件是 **Platform Policy**，强制注入；Agent 不可选择跳过。
> 观察/报告手法见 Methodology Skill：`playtest/observation`。

生成后由 **CodeQaLoop** 对当前 candidate 做 **Playwright 可交互冒烟**，不靠 LLM 自评，也不允许静态 DOM 检测冒充通过。

## 试玩检查项（须全部满足）

1. **Playwright + Chromium 可用**（否则 `failure_kind=infra`）
2. **页面加载成功**，无未捕获 `pageerror`
3. **模拟输入**：`ArrowRight` / `Space`（及可见按钮 click）不得崩溃
4. **运行弱信号**至少一种：`raf` / `canvas_diff` / `engine_runtime`

## 失败处理

- 每轮结果写入 `qa_report`（`passed`、`attempt`、`issues`、`console_logs`、`failure_kind`、`motion_signal`、`playtest_mode=playwright`）
- 在 `code_qa_max_attempts`（默认 3，含首次 generate）内：
  - `product` / `build` → diagnose → repair → 再测
  - `infra` → **不**修源码，仅重测同一 candidate
- 耗尽后进入 **`qa_failed` HITL**（`status=PAUSED`），用户可通过 `hitl/resolve` 或 `/retry` 恢复；resume 后 attempt 从 1 重新计数

## 实现

- `app.sandbox.playtest.run_playtest` / `run_playtest_dist`
- 子图：`app.forge.subgraphs.code_qa_loop`
- 静态检查仅作诊断 helper，**不得**作为生产 `qa_ok=true` 路径
