# ADR Batch A（P0 安全 / Worker / 超时）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 落地 ADR-07/08/09 上线前必做项：JWT 启动门禁、manifest 覆盖防护、verify-email 限流、OAuth 绑定校验、SSRF 主机限制、dev 路由显式开关、compose restart、worker 消息路径加固、基建超时与节点 Retry/Timeout 策略。

**架构：** 安全校验下沉到 `config` / `manifest` / `auth` / `llm` 纯函数或服务层；worker 在 `_run_one` / `_consume` 加兜底；超时进 `config` + `db`/`redis`/`policy`/`guard`。本切片**不含**：pnpm store 租户隔离、配额中途预扣、trial 全端拦截、邮件独立队列、checkpoint 重投恢复（留给 Batch B / 后续 PR）。

**技术栈：** FastAPI、Pydantic Settings、pytest、asyncio、aio_pika、LangGraph policies、docker-compose。

**规格：** `docs/adr/ADR-07-*.md`、`ADR-08-*.md`、`ADR-09-*.md`、`ADR-MODIFICATION-GUIDE-2026-08-16.md`

---

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `backend/app/core/config.py` | `jwt` 门禁、`dev_routes_enabled`、DB/Redis/Docker 超时配置项 |
| `backend/app/core/security_boot.py`（新建） | `assert_production_secrets()` 启动校验 |
| `backend/app/main.py` | lifespan 调用门禁；dev 路由挂载条件 |
| `backend/app/forge/build/manifest.py` | `PROTECTED_WORKSPACE_FILES` + merge 过滤 |
| `backend/app/sandbox/builder.py` | `packageManager` 正则白名单 |
| `backend/app/api/auth.py` | verify-email 限流 |
| `backend/app/auth/services.py` | 验证码失败计数作废 |
| `backend/app/auth/oauth.py` | `email_verified` 绑定门槛 |
| `backend/app/llm/url_safety.py`（新建） | `base_url` SSRF 校验 |
| `backend/app/llm/services.py` | 调用 URL 校验 |
| `backend/app/messaging/worker.py` | decode/DLQ try、busy 退避、consume 重连 |
| `docker-compose.yml` | `restart: unless-stopped`；RabbitMQ `consumer_timeout` |
| `backend/app/core/db.py` / `redis.py` | 连接/命令超时 |
| `backend/app/forge/reliability/policy.py` | `done` 策略、`retry_on`、code_or_repair 动态预算入口 |
| `backend/app/forge/graph.py` | `done` 挂 TimeoutPolicy |
| `backend/app/forge/guard.py` | audit `wait_for` |

---

### 任务 1：JWT 生产门禁（ADR-07 §1 / P0-1）

**文件：**

- 创建：`backend/app/core/security_boot.py`
- 修改：`backend/app/main.py`（lifespan）、`backend/app/messaging/worker.py`（main 启动）
- 测试：`backend/tests/test_security_boot.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security_boot import assert_production_secrets, DEFAULT_JWT_SECRET


def test_assert_rejects_default_jwt_in_production() -> None:
    s = Settings(env="production", jwt_secret=DEFAULT_JWT_SECRET)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets(s)


def test_assert_rejects_short_jwt_in_production() -> None:
    s = Settings(env="staging", jwt_secret="x" * 16)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets(s)


def test_assert_allows_default_in_development() -> None:
    s = Settings(env="development", jwt_secret=DEFAULT_JWT_SECRET)
    assert_production_secrets(s)  # no raise


def test_assert_allows_strong_secret_in_production() -> None:
    s = Settings(env="production", jwt_secret="a" * 32)
    assert_production_secrets(s)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && uv run pytest tests/test_security_boot.py -v`
预期：FAIL（模块不存在）

- [ ] **步骤 3：编写最少实现**

`security_boot.py`：

```python
DEFAULT_JWT_SECRET = "dev-secret-change-me-to-a-32-byte-random-string"

def assert_production_secrets(settings) -> None:
    if settings.env == "development":
        return
    secret = (settings.jwt_secret or "").strip()
    if secret == DEFAULT_JWT_SECRET or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a non-default value of at least 32 characters "
            f"when env={settings.env!r}"
        )
```

`main.py` lifespan 开头与 `worker.py` `main()` 启动处调用 `assert_production_secrets(settings)`。

- [ ] **步骤 4：运行测试验证通过**

`uv run pytest tests/test_security_boot.py -v` → PASS

- [ ] **步骤 5：Commit**

`test(security): add JWT production fail-fast boot checks`
`feat(security): reject default JWT_SECRET outside development`

---

### 任务 2：manifest 黑名单 + packageManager 白名单（ADR-07 §2 / P0-2）

**文件：**

- 修改：`backend/app/forge/build/manifest.py`、`backend/app/sandbox/builder.py`
- 测试：`backend/tests/test_build_p2.py`（追加）或 `backend/tests/test_manifest_protect.py`

- [ ] **步骤 1：失败测试**

```python
from app.forge.build.manifest import merge_workspace, generate_manifest_files
from app.forge.build.types import BuildRouting  # 按仓库实际类型导入

def test_merge_workspace_ignores_protected_overrides(routing_fixture):
    base = generate_manifest_files(routing_fixture)
    poisoned = {
        "package.json": '{"name":"evil"}',
        "pnpm-workspace.yaml": "packages:\n  - evil",
        "vite.config.ts": "export default {}",
        "src/main.ts": "console.log(1)",
    }
    ws = merge_workspace(routing_fixture, poisoned)
    assert ws["package.json"] == base["package.json"]
    assert ws["src/main.ts"] == "console.log(1)"
```

```python
from app.sandbox.builder import corepack_activate_shell, sanitize_package_manager_version
from pathlib import Path

def test_sanitize_package_manager_rejects_injection(tmp_path: Path):
    assert sanitize_package_manager_version("pnpm@9.15.0") == "9.15.0"
    assert sanitize_package_manager_version("pnpm@9.15.0; rm -rf /") is None
    assert sanitize_package_manager_version("yarn@1.0.0") is None
```

- [ ] **步骤 2：跑测确认 FAIL**
- [ ] **步骤 3：实现**

`manifest.py`：

```python
import fnmatch

PROTECTED_WORKSPACE_FILES = frozenset({
    "package.json",
    "pnpm-workspace.yaml",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "tsconfig.json",
    "build-profile.json",
})
PROTECTED_WORKSPACE_GLOBS = ("vite.config.*",)

def _is_protected(name: str) -> bool:
    if name in PROTECTED_WORKSPACE_FILES:
        return True
    return any(fnmatch.fnmatch(name, g) for g in PROTECTED_WORKSPACE_GLOBS)

def merge_workspace(...):
    workspace = dict(generate_manifest_files(routing, profile))
    for rel, content in source_files.items():
        if _is_protected(rel.replace("\\", "/").lstrip("./")):
            continue
        workspace[rel] = content
    ...
```

`builder.py`：`re.fullmatch(r"pnpm@\d+(\.\d+)*", pm)` 后才取版本。

- [ ] **步骤 4：PASS**
- [ ] **步骤 5：Commit** `fix(build): block LLM overrides of platform manifest files`

---

### 任务 3：verify-email 限流 + 失败作废（ADR-07 §3 / P1-17）

**文件：**

- 修改：`backend/app/api/auth.py`、`backend/app/auth/services.py`、`backend/app/core/config.py`（可选阈值）
- 测试：`backend/tests/test_auth.py` 追加

- [ ] **步骤 1：** 为 `verify_email` 路由加与 login 同级 `check_rate_limit`（IP + 邮箱归一化键）。
- [ ] **步骤 2：** `services.verify_email`：失败时 Redis/DB 计数；达 `verify_email_max_failures`（默认 5）则 `used_at` 作废所有 pending 码并抛明确错误。
- [ ] **步骤 3：** 测试：无限流键时 429；失败 N 次后旧码失效。
- [ ] **步骤 4：Commit** `fix(auth): rate-limit verify-email and invalidate after failures`

---

### 任务 4：OAuth 仅绑定已验证邮箱（ADR-07 §3 / P1-18）

**文件：** `backend/app/auth/oauth.py`
**测试：** `backend/tests/test_oauth_bind.py`（新建，mock db）

- [ ] existing 用户且 `email_verified is False` → 抛 `AppError`（FORBIDDEN/VALIDATION），不 `add(OAuthAccount)`。
- [ ] `email_verified is True` → 现有绑定行为保留。
- [ ] Commit：`fix(auth): require email_verified before OAuth email bind`

---

### 任务 5：openai_compat base_url SSRF 防护（ADR-07 §4 / P1-19）

**文件：**

- 创建：`backend/app/llm/url_safety.py`
- 修改：`backend/app/llm/services.py`
- 测试：`backend/tests/test_url_safety.py`

- [ ] 允许：`https://api.openai.com`；development 允许 `http://127.0.0.1:11434`。
- [ ] 拒绝：`http://169.254.169.254/`、`http://10.0.0.1`、`http://192.168.1.1`、非 http(s)。
- [ ] `test_draft_config` / `create_config` 在发请求前调用。
- [ ] Commit：`fix(llm): block private and metadata hosts in openai_compat base_url`

---

### 任务 6：dev 路由显式开关（ADR-07 §5 / P1-20）

**文件：** `config.py`、`main.py`、`.env.example`
**测试：** `backend/tests/test_dev_routes_gate.py`

- [ ] 新增 `dev_routes_enabled: bool = False`。
- [ ] 挂载条件：`settings.dev_routes_enabled`（不再仅靠 `env == "development"`）。
- [ ] `.env.example` 注明本地可开；生产必须关。
- [ ] 调整依赖 `env==development` 的现有测试（conftest 设 `DEV_ROUTES_ENABLED=true`）。
- [ ] Commit：`fix(api): gate /dev routes behind DEV_ROUTES_ENABLED`

---

### 任务 7：Compose restart + RabbitMQ consumer_timeout（ADR-08 §1/§2A）

**文件：** `docker-compose.yml`

- [ ] `backend` / `worker` 加 `restart: unless-stopped`。
- [ ] `rabbitmq` environment：`RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS: -rabbit consumer_timeout 7200000`（或等价，≥ 2h，覆盖 code_qa 外墙）。
- [ ] Commit：`chore(compose): restart workers and raise consumer_timeout`

---

### 任务 8：Worker 消息路径加固（ADR-08 §1/§3/§4）

**文件：** `backend/app/messaging/worker.py`
**测试：** `backend/tests/test_worker_run_one.py`（对 `_run_one` 用假 message）

- [ ] `decode_task` 纳入 try；解码失败记日志并 `_publish_to_dlq`（或显式吞并 ack）。
- [ ] `_republish_task` / `_publish_to_dlq` 外层 try/except + `log.exception`；失败不二次抛死进程。
- [ ] `TaskLeaseBusy`：`retry` 递增或使用 `min(60, 2 ** retry)` sleep，且受 `worker_max_redeliveries` 约束后进 DLQ。
- [ ] `_consume` 外层：连接/循环异常 → sleep 退避 → 重连（不要直接 `main` 退出后无 restart 依赖；compose 已补 restart 仍要代码层重连）。
- [ ] Commit：`fix(worker): harden decode/DLQ paths and lease-busy backoff`

---

### 任务 9：基建超时 + done TimeoutPolicy + audit wait_for + retry_on（ADR-09）

**文件：** `config.py`、`db.py`、`redis.py`、`policy.py`、`graph.py`、`guard.py`
**测试：** `backend/tests/test_reliability_policy.py`、`test_guard_audit_timeout.py`

- [ ] config 增加：`db_pool_timeout`、`db_command_timeout`、`redis_socket_timeout`、`redis_connect_timeout`（合理默认，如 10/60/5/5）。
- [ ] `create_async_engine(..., connect_args={"timeout": ..., "command_timeout": ...})`（asyncpg）。
- [ ] Redis pool：`socket_connect_timeout` / `socket_timeout`。
- [ ] `NODE_EXECUTION_POLICIES["done"] = NodeExecutionPolicy(fixed_run_timeout_s=30, max_attempts=1)`；`graph` 对 `done` 使用 `_node_kwargs("done")`。
- [ ] `langgraph_retry_policy`：`retry_on` 排除 `AppError`、`ContentAttacked`、`RunFinalized`（按仓库实际异常类导入）。
- [ ] `guard.audit` 调用包 `asyncio.wait_for(..., settings.audit_request_timeout)`。
- [ ] `code_or_repair`：若 `build_pipeline_enabled`，`resolve_node_run_timeout` 加上 `build_max_retries * builder_timeout_s` 量级裕量。
- [ ] Commit：`fix(reliability): unify IO timeouts and node retry_on policy`

---

## 本计划明确延后（勿在本 PR 膨胀）

| 项 | 原因 |
| --- | --- |
| P1-21 store 租户隔离 | 需构建架构改动，属 ADR-11 交叉 |
| P1-22/23 配额中途 + trial 全拦 | 触面广，可单独 PR |
| P1-4/5/6/7 checkpoint HITL | Batch B / ADR-10 |
| P1-8 邮件独立队列 | 需 broker 拓扑变更 |
| P1-24～26 前端 | ADR-12 Section A |

---

## 验证总清单

```bash
cd backend && uv run pytest tests/test_security_boot.py tests/test_manifest_protect.py tests/test_url_safety.py tests/test_auth.py tests/test_dev_routes_gate.py tests/test_reliability_policy.py -q
cd backend && uv run ruff check app/core/security_boot.py app/forge/build/manifest.py app/sandbox/builder.py app/messaging/worker.py app/llm/url_safety.py
```

---

## 自检

- ADR-07 §1–5 → 任务 1–6
- ADR-08 §1、§2A、§3、§4 busy → 任务 7–8
- ADR-09 核心 → 任务 9
- 无「TODO/后续补充」占位任务
