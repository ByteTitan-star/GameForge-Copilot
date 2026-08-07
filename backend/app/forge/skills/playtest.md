# QA 试玩约定（B1）

生成完成后，QA 阶段在沙箱内对 `index.html` 做**真实试玩**，不靠 LLM 自评。

## 试玩检查项

1. **无 JS 运行时错误**（pageerror / console error）
2. **可玩元素存在**：`<canvas>` 或 button/input/onclick 等交互控件
3. **模拟输入**：发送 `ArrowRight`、`Space` keydown，不得抛异常

## 失败处理

- 试玩结果写入 `qa_report` WS 事件（含 `errors[]`、`console_logs[]`）
- 在 `qa_max_retries` 内自动回退 `code_node` 修复
- 重试耗尽后进入 `qa_failed` HITL，由人工决定 approve/reject/modify

## 实现

- `app.sandbox.playtest.run_playtest(html)` → `{ ok, errors[], console_logs[] }`
- 默认静态 DOM 检测；生产可设 `PLAYTEST_USE_PLAYWRIGHT=1` 启用 Chromium
