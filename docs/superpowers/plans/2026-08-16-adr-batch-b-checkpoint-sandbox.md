# ADR Batch B（Checkpoint / HITL / Sandbox·Hosting）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 落地 ADR-10 + ADR-11 一周内必做项：promote 两段式幂等、暂停检查点合并与恢复路由、resume_grant 延迟消费、RUNNING 超时回收、HITL 词表单点、checkpoint revision 校验、resolve 锁/条件更新；以及 failure_kind 贯通、Docker 生命周期与日志有界、孤儿清扫、本地进程组、路径纵深、Docker uid/tier 表收敛、HostingBackend layers、WS relay finally。

**架构：** HITL/checkpoint 域能力下沉到 `forge/hitl.py` + `reliability/idempotency.py` + `forge/state.py` + `scheduler`；sandbox/hosting 在 `BuildResult` / HostConfig / `HostingBackend` 协议层补齐。本切片**不含**：E2B `_LIVE` 持久化对账、OSS 全量 prune 治理、`resolve_hitl` 整段搬迁 services（仅抽常量 + try/finally + 条件 UPDATE）、ADR-12 前端债。

**技术栈：** FastAPI、SQLAlchemy、Redis、pytest、asyncio、aiodocker、WebSocket。

**规格：** `docs/adr/ADR-10-*.md`、`ADR-11-*.md`、`ADR-05` 修订、`ADR-MODIFICATION-GUIDE-2026-08-16.md`
**打包：** 单 PR（方案 1）

---

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `backend/app/forge/hitl.py`（新建） | `HITL_PHASES`、phase→allowed decisions、`is_hitl_phase` |
| `backend/app/forge/reliability/idempotency.py` | `commit_side_effect` / pending→done；可选 `clear_side_effect` |
| `backend/app/forge/graph.py` | promote 两段式；延迟消费 grant；`user_pause` 恢复路由 |
| `backend/app/forge/reliability/pause.py` | `merge_pause_checkpoint(existing, ...)` |
| `backend/app/forge/state.py` | `load_state` 比对 DB revision；commit 后再写 Redis（或校验） |
| `backend/app/scheduler/services.py` | `expire_stale_running_runs` |
| `backend/app/core/config.py` | `running_stale_timeout_s`、container log tail、tier 表入口 |
| `backend/app/api/runs.py` | 消费 `hitl` 模块；resolve 锁 finally；条件 UPDATE |
| `backend/app/sandbox/base.py` | `BuildResult.failure_kind` |
| `backend/app/sandbox/docker.py` / `builder.py` | AutoRemove、LogConfig、log `tail`、uid、failure_kind |
| `backend/app/sandbox/tiers.py` 或 `sandbox/resources.py` | tier→资源/超时单表 |
| `backend/app/sandbox/local.py` / `builder.py` Local | `start_new_session` + kill 进程组 |
| `backend/app/sandbox/cleanup.py`（新建） | 孤儿容器/临时目录清扫 |
| `backend/app/messaging/worker.py` | 启动时调用 cleanup |
| `backend/app/hosting/backend.py` / `local.py` / `s3.py` / `store.py` | `write_version_layers` 进协议 |
| `backend/app/ws/runs.py` | relay 全路径 try/finally |
| `backend/app/forge/build/*` 或 write 路径 | workspace `rel` 规范化校验（若尚缺） |

---

### 任务 1：HITL 词表单点（ADR-10 §4）

**文件：**

- 创建：`backend/app/forge/hitl.py`
- 修改：`backend/app/api/runs.py`、`backend/app/forge/graph.py`、`backend/app/dev/runtime.py`（若有复制）
- 测试：`backend/tests/test_hitl_vocab.py`

- [ ] **步骤 1：编写失败的测试**

```python
from app.forge.hitl import HITL_PHASES, allowed_decisions_for, is_hitl_phase


def test_hitl_phases_cover_confirm_and_failures() -> None:
    assert HITL_PHASES == frozenset(
        {"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"}
    )


def test_allowed_decisions() -> None:
    assert allowed_decisions_for("plan_confirm") == frozenset({"approve", "modify"})
    assert "select_a" in allowed_decisions_for("art_confirm")


def test_is_hitl_phase() -> None:
    assert is_hitl_phase("plan_confirm")
    assert not is_hitl_phase("user_pause")
```

- [ ] **步骤 2：** `uv run pytest tests/test_hitl_vocab.py -v` → FAIL（模块不存在）

- [ ] **步骤 3：实现 `hitl.py` 并替换各处硬编码集合**

```python
HITL_PHASES = frozenset({"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"})

_ALLOWED: dict[str, frozenset[str]] = {
    "plan_confirm": frozenset({"approve", "modify"}),
    "art_confirm": frozenset({"select_a", "select_b", "modify"}),
    "sandbox_failed": frozenset({"approve", "modify"}),
    "qa_failed": frozenset({"approve", "modify"}),
}

def is_hitl_phase(phase: str | None) -> bool:
    return phase in HITL_PHASES

def allowed_decisions_for(phase: str) -> frozenset[str]:
    return _ALLOWED[phase]
```

- [ ] **步骤 4：** 测试 PASS

- [ ] **步骤 5：Commit** `feat(hitl): centralize HITL phase vocabulary`

---

### 任务 2：Promote 两段式幂等（ADR-10 §1）

**文件：**

- 修改：`backend/app/forge/reliability/idempotency.py`、`backend/app/forge/graph.py`（promote 调用处）
- 测试：`backend/tests/test_promote_idempotency.py`

- [ ] **步骤 1：测试**

```python
import pytest
from app.forge.reliability.idempotency import (
    try_begin_side_effect,
    commit_side_effect,
    side_effect_status,
)

@pytest.mark.asyncio
async def test_pending_allows_retry_after_crash(fake_redis):
    key = "forge:side:test:promote"
    assert await try_begin_side_effect(fake_redis, key, value="pending")
    assert await side_effect_status(fake_redis, key) == "pending"
    # 模拟崩溃：未 commit；重放应视为未完成
    assert not await try_begin_side_effect(fake_redis, key, value="pending")
    assert await side_effect_status(fake_redis, key) == "pending"
    await commit_side_effect(fake_redis, key)
    assert await side_effect_status(fake_redis, key) == "done"
```

- [ ] **步骤 2：** FAIL（缺 API）

- [ ] **步骤 3：实现**

- `try_begin_side_effect` 默认仍可写 `"1"`；promote 路径显式 `value="pending"`
- 新增 `commit_side_effect(r, key)` → set value `"done"`（保持 TTL）
- 新增 `side_effect_status` → `None | "pending" | "done" | other`
- graph promote：

```python
key = side_effect_key(...)
began = await try_begin_side_effect(ctx.r, key, value="pending")
status = await side_effect_status(ctx.r, key)
if began or status == "pending":
    await ctx.s.refresh(ctx.game)
    if ctx.game.current_version != int(version):
        promote_candidate(ctx.game, int(version))
        await ctx.s.commit()
    await commit_side_effect(ctx.r, key)
else:
    await ctx.s.refresh(ctx.game)
    if ctx.game.current_version != int(version):
        promote_candidate(ctx.game, int(version))
        await ctx.s.commit()
        await commit_side_effect(ctx.r, key)
```

- [ ] **步骤 4–5：** PASS + commit `fix(reliability): two-phase promote side-effect idempotency`

---

### 任务 3：暂停检查点合并 + user_pause 恢复路由（ADR-10 §2）

**文件：**

- 修改：`backend/app/forge/reliability/pause.py`、`games/services.py`、`graph.py` `route_start`
- 测试：`backend/tests/test_pause_checkpoint_merge.py`

- [ ] **步骤 1：测试**

```python
from app.enums import PauseReason
from app.forge.reliability.pause import merge_pause_checkpoint

def test_merge_preserves_art_and_code_progress():
    existing = {
        "phase": "code",
        "design_doc": {"title": "t"},
        "art_options": {"options": [1]},
        "attempt": 2,
        "artifacts": ["a"],
    }
    out = merge_pause_checkpoint(
        existing,
        phase="user_pause",
        pause_reason=PauseReason.MANUAL_HOLD,
    )
    assert out["art_options"] == {"options": [1]}
    assert out["attempt"] == 2
    assert out["phase"] == "user_pause"
    assert out["pause_reason"] == PauseReason.MANUAL_HOLD.value
```

- [ ] **步骤 3：实现 `merge_pause_checkpoint`**

以 `existing` 为底，覆盖 `phase` / `pause_reason` / 可选 `design_doc` / `recovery`；默认去掉冲突的 `recovery`（manual hold）；`games.pause_run` 与 graph 暂停统一调用。

`route_start` 中 `user_pause`：按检查点进度续跑（有 `candidate_version`/`attempt` → `code_qa_loop`；有 `art_options` 未确认 → 勿无条件 `art_options`；否则按 `phase` 映射），**禁止**无条件 `return "art_options"`。

- [ ] **步骤 5：** commit `fix(forge): merge pause checkpoints and resume user_pause by progress`

---

### 任务 4：resume_grant 延迟消费（ADR-10 §3）

**文件：**

- 修改：`backend/app/forge/graph.py` `_run_body`
- 测试：扩展 `backend/tests/test_runs.py` 或新建 `test_resume_grant.py`

行为变更：

1. HITL 阶段：`grant = st.get("resume_grant")`（**不 pop**）；无 grant → 跳过（保持现状）。
2. 有 grant：用其 decision/modify_text，**暂不**从 checkpoint 删除；设 RUNNING 并跑图。
3. 图内首次成功离开 HITL 等待语义后（进入下一节点并写出非 HITL phase，或 HITL pause 再次写入前）：`consume_resume_grant` 删除字段并 `save_state`。
4. 若 worker 在消费前崩溃：grant 仍在 → 重投可再次推进。

最小实现钩子：在 `_run_body` 于 `graph.ainvoke` **成功返回且未因 stale 提前 return** 后清除 grant；若 invoke 抛错则保留 grant。若 invoke 成功但再次 HITL pause，清除旧 grant（新一轮需新 enqueue）。

- [ ] Commit：`fix(forge): delay resume_grant consumption until run advances`

---

### 任务 5：RUNNING 超时回收（ADR-10 §3）

**文件：**

- 修改：`backend/app/core/config.py`（`running_stale_timeout_s`，默认建议 `max(hil 相关, 30*60)` 或显式 3600）、`scheduler/services.py`、`messaging/worker.py` 周期任务
- 测试：`backend/tests/test_expire_stale_running.py`

逻辑：

```python
async def expire_stale_running_runs(db, r) -> int:
    cutoff = now - timedelta(seconds=settings.running_stale_timeout_s)
    rows = select RUNNING, ended_at IS NULL, updated_at <= cutoff
    for run in rows:
        if r and await r.exists(f"run:executing:{run.id}"):
            continue  # 租约仍在，跳过
        # → FAILED + 消息 + clear checkpoint + cancel tasks（对齐 PAUSED 回收）
```

- [ ] Commit：`fix(scheduler): reclaim stale RUNNING runs without exec lease`

---

### 任务 6：Checkpoint revision 校验（ADR-10 §5）

**文件：**

- 修改：`backend/app/forge/state.py`（Redis 缓存带 revision；`load_state` 比对）
- 测试：`backend/tests/test_checkpoint_revision.py`

缓存 JSON 形态：`{"revision": N, "state": {...}}`（或并行 key `run:ckpt:rev:{id}`）。`load_state`：若 Redis 有数据但 revision ≠ DB → 弃缓存读 DB 并回填。`save_state`：DB flush 成功后再写 Redis。

- [ ] Commit：`fix(forge): validate checkpoint cache against DB revision`

---

### 任务 7：resolve_hitl 锁 finally + 条件 UPDATE（ADR-10 §6）

**文件：**

- 修改：`backend/app/api/runs.py`
- 测试：扩展 `test_runs.py`（可用 monkeypatch 模拟异常确保锁释放；条件更新用 status 断言）

```python
lock_key = f"run:hitl:{run_id}"
if not await r.set(lock_key, "1", nx=True, ex=60):
    raise AppError(...)
try:
    ...
    result = await db.execute(
        update(GenerationRun)
        .where(GenerationRun.id == run_id, GenerationRun.status == RunStatus.PAUSED.value)
        .values(status=RunStatus.RUNNING.value, ended_at=None)
    )
    if result.rowcount != 1:
        raise AppError(ErrorCode.INVALID_STATE, "run 已结束或不在 paused")
    ...
finally:
    await r.delete(lock_key)
```

- [ ] Commit：`fix(api): HITL resolve lock finally and conditional status update`

---

### 任务 8：BuildResult.failure_kind（ADR-11 §1）

**文件：**

- 修改：`backend/app/sandbox/base.py`、`docker.py`、`builder.py`、code_qa 消费处（若依赖字符串嗅探则改为读字段）
- 测试：`backend/tests/test_build_failure_kind.py`

```python
@dataclass
class BuildResult:
    ok: bool
    files: dict[str, bytes] = field(default_factory=dict)
    logs: str = ""
    error: str | None = None
    failure_kind: Literal["infra", "build", "timeout", "oom"] | None = None
```

DockerError / pull 失败 → `infra`；超时 → `timeout`；OOM 日志 → `oom`；退出码非 0 → `build`。Repair 循环对 `infra`/`timeout`（按现有 playtest 策略）不得当 product 烧修。

- [ ] Commit：`feat(sandbox): structured failure_kind on BuildResult`

---

### 任务 9：Docker HostConfig + 有界日志 + 孤儿清扫（ADR-11 §2）

**文件：**

- 修改：`docker.py`、`builder.py` HostConfig 增加 `AutoRemove`、`LogConfig`
- `container.log(..., tail=settings.sandbox_log_tail)`（默认 2000）
- 新建 `sandbox/cleanup.py`：列出 `gf-sandbox-*` / `gf-builder-*` 强制删；清 `gf-*-sandbox-*` tempfile 前缀目录
- `worker.py` 启动调用一次

- [ ] Commit：`fix(sandbox): AutoRemove, log bounds, and orphan cleanup`

---

### 任务 10：本地进程组 + 路径纵深（ADR-11 §3）

**文件：**

- `local.py` / `LocalBuilder`：POSIX `start_new_session=True`；超时时 `os.killpg`；Windows 文档化 `proc.kill()` 兜底
- 写文件路径：复用/抽出 `_check_path` 到共享工具，ensure_workspace_rel

- [ ] Commit：`fix(sandbox): process group kill and workspace path containment`

---

### 任务 11：Docker uid + tier 单表（ADR-11 §4）

**文件：**

- 抽出 `sandbox/resources.py`：`TIER_LIMITS` 供 docker/local/builder 读取
- `DockerSandbox` HostConfig 加 `User: _docker_user_spec()`（与 builder 共享）
- 测试：`test_tier_limits_single_source.py`

- [ ] Commit：`refactor(sandbox): unify tier resource table and docker user`

---

### 任务 12：HostingBackend.write_version_layers（ADR-11 §5）

**文件：**

- Protocol 增加方法；`local` 已有实现；`s3` 实现等价上传三层；`store.write_version_layers` 改为 `get_hosting_backend().write_version_layers(...)`
- 测试：扩展 `test_hosting_layers.py` / `test_s3_hosting.py`（mock）

- [ ] Commit：`fix(hosting): route write_version_layers through HostingBackend`

---

### 任务 13：WS relay 生命周期（ADR-11 §6）

**文件：**

- 修改：`backend/app/ws/runs.py`
- 测试：`backend/tests/test_ws_relay_lifecycle.py`（异步 mock：replay 中断开仍 cancel relay）

```python
relay = asyncio.create_task(...)
try:
    await ready.wait()
    await _replay_buffered(...)
    replayed.set()
    disc = asyncio.create_task(_await_disconnect(websocket))
    ...
finally:
    relay.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await relay
```

- [ ] Commit：`fix(ws): cancel relay across ready/replay/disconnect`

---

## 明确 defer

| 项 | 原因 |
| --- | --- |
| E2B 会话持久化对账（ADR-11 §7） | Non-goal；生产保持 Docker |
| OSS prune 全链路 | 需独立运维设计 |
| `resolve_hitl` 整段迁 services | 本切片用 finally + 条件 UPDATE 满足 P2-12 |
| ADR-12 前端 | Batch C |

---

## 验证清单

```bash
cd backend
uv run pytest tests/test_hitl_vocab.py tests/test_promote_idempotency.py \
  tests/test_pause_checkpoint_merge.py tests/test_checkpoint_revision.py \
  tests/test_expire_stale_running.py tests/test_build_failure_kind.py \
  tests/test_ws_relay_lifecycle.py tests/test_runs.py -q
```

全量相关：`tests/test_hosting*.py`、`tests/test_code_qa_loop.py`、`tests/test_sandbox*.py`
