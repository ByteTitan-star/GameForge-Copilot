# Forge 编排边界优化（对照技术选型）

> 状态：P0 + P1 + P2（部分）已落地。

## P0（已完成）

1. 等待态去副作用（`_commit_hitl_side_effects` → Wait State）
2. Checkpoint 瘦身（plan / art / art_options revision id）
3. Run 级 token 熔断（`FORGE_RUN_MAX_TOKENS`，默认 500000）

## P1（已完成）

1. `RunStatus.cancelled` 一等终态；取消保留瘦 checkpoint
2. Revision 回流：`revise_plan` → `force_new_plan` + STALE

## P2（已完成）

1. **`art_options` ArtifactRevision** + checkpoint 瘦身
2. **确定性 HTML 结构门禁**（空页 / 无 script / eval）
3. **策划稿静态验收门禁**（`FORGE_ACCEPTANCE_GATE=true`）
   - 引擎表面（canvas/phaser/pixi）、键盘/触控事件、分数 HUD、多屏状态痕迹
   - 在 `run_playtest` / `run_playtest_dist` 进浏览器前执行
4. **策划稿运行时验收探针**（`FORGE_ACCEPTANCE_RUNTIME=true`）
   - 解析 `acceptance_criteria.verification`：开始后应进入 playing、暂停探针
   - 终态：`__AG_CHEAT__` 可调用时断言 `game_over` / `level_complete` / `victory` 切换
   - 无 cheat 时终态仅做源码引用检查
5. **美术 A/B 真并行**（`FORGE_ART_OPTIONS_PARALLEL=true`）
   - A/B 各一次 LLM（`asyncio.gather`），再 `merge_parallel_art_options`
   - 关开关则回退单次返回两套；失败仍走原有重试与素材兜底

## 配置

```env
FORGE_RUN_MAX_TOKENS=500000
FORGE_ART_OPTIONS_PARALLEL=true
FORGE_ACCEPTANCE_GATE=true
FORGE_ACCEPTANCE_RUNTIME=true
```

## 仍未做

- LangGraph 原生 interrupt
