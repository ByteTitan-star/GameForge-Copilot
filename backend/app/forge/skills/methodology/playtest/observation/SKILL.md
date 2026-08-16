---
id: playtest/observation
name: Playtest Observation
kind: methodology
nodes: [repair, qa, diagnose]
---

# 试玩观察方法论（非门禁）

本 Skill 只指导如何观察与报告证据；**不得**替代 B 档 Playwright 门禁，也不得据此宣称 `qa_ok`。

- 记录输入序列（方向键 / Space / 点击）与崩溃时机。
- 关注运动弱信号：`raf` / `canvas_diff` / `engine_runtime` 是否出现。
- 区分 infra（浏览器/沙箱不可用）与 product（逻辑错误）。
- 诊断输出应给出可复现步骤与可疑代码位置，而非空泛建议。
