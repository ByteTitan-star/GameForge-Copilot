# QA 试玩约定（B1）

生成完成后，QA 阶段在沙箱内对 `index.html` 做**真实试玩**，不靠 LLM 自评。

## 试玩检查项

1. **无 JS 运行时错误**（pageerror / console error）
2. **可玩元素存在**：`<canvas>` 或 button/input/onclick 等交互控件
3. **模拟输入**：发送 `ArrowRight`、`Space` keydown，不得抛异常

## 失败处理

- 试玩结果写入 `qa_report` WS 事件（含 `errors[]`、`console_logs[]`）
- 在 `qa_max_retries` 内：先由 QA 负责人做根因诊断，再以当前可运行版本为基线
  回退 `code_node` 做定向修复（而非从零重生成）
- 重试耗尽后直接判定失败（FAILED，code=`QA_RETRY_EXHAUSTED`），不再进入人工
  确认 HITL；用户可经 `/retry` 重投，或修改需求后重新发起

## 实现

- `app.sandbox.playtest.run_playtest(html)` → `{ ok, errors[], console_logs[] }`
- 默认静态 DOM 检测；生产可设 `PLAYTEST_USE_PLAYWRIGHT=1` 启用 Chromium
