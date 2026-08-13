# 「联系管理员」改造设计

- 日期：2026-08-13
- 分支：feature/engine-routing
- 状态：已批准，待实现

## 1. 目标

把 forge 页面失败恢复条里的「联系管理员」按钮，从 `mailto:` 调起系统邮件客户端，改成「弹一个输入框 → 前端调后端 → 后端代发邮件给管理员」，用户全程不接触管理员邮箱地址。发送成功后弹 toast 告知用户。

### 范围约束（YAGNI）

- **可见范围不变**：该按钮仍只在 forge 运行**失败**时出现（`FailureRecoveryBar`，`runStatus === failed`）。不做常驻入口、不做全局反馈。
- **复用现有基础设施，不造轮子**：邮件发送复用 `app/email/queue.py::enqueue_notification`；管理员邮箱复用 `app/admin/services.py::get_admin_contact_email`；限流复用 `app/auth/ratelimit.py::check_rate_limit`；run 查询与归属校验复用 `app/games/services.py::get_run`。
- **不新增配置项、不新增任务类型、不新增依赖**。

## 2. 关键事实（已核实）

| 关注点 | 现状 | 来源 |
|---|---|---|
| 按钮当前行为 | `window.location.href = mailto:<VITE_SUPPORT_EMAIL>?...`，调起系统邮件客户端 | `frontend/src/components/forge/FailureRecoveryBar.tsx:49-56` |
| 按钮出现条件 | 仅 forge 失败、底部日志带展开后随 `FailureRecoveryBar` 出现 | `ForgePage.tsx:209` `showFailureRecovery` |
| `errorSummary` 来源 | **前端运行时状态** `runErrors[runId]`（WS/重试响应），**不是 DB 字段** | `ForgePage.tsx:210`；`GenerationRun` model 无错误摘要列 |
| 邮件代发通道 | 已有异步 SMTP worker，业务侧调 `enqueue_notification(email, subject, body)` | `backend/app/email/queue.py:37` |
| 管理员邮箱解析 | `get_admin_contact_email(db)`：DB 系统设置 > `ADMIN_CONTACT_EMAIL` 环境变量 > 第一个 admin 邮箱 > 兜底 | `backend/app/admin/services.py:24` |
| 限流工具 | Redis ZSET 滑动窗口 `check_rate_limit(r, key, limit, window_s)`，超限抛 `RATE_LIMITED` | `backend/app/auth/ratelimit.py`；范例 `backend/app/api/auth.py:register` |
| run 查询 + 归属校验 | `get_run(db, user, run_id)` 带 `user_id == user.id`，不存在抛 `GAME_NOT_FOUND` | `backend/app/games/services.py:437` |
| 前端 API 客户端 | `frontend/src/api/client.ts`，按业务域拆模块；项目用自研组件（无 shadcn） | `api/games.ts`、`components/forge/*` |
| 路由组织 | 一文件一 router，`app.include_router(x, prefix=API_V1)` 集中注册于 `main.py:96` | `backend/app/main.py` |

### 设计权衡记录：错误摘要从哪来

初步设想是「后端查 DB 补错误摘要」，但核实后发现 `GenerationRun` model **不持久化**失败原因，错误摘要是前端运行时状态。因此本设计改为：

- **后端邮件正文只带可靠信息**：runId（`get_run` 查 DB 拿到）、用户 id、用户留言。
- **错误摘要由前端可选传入**：作为请求体的可选字段 `error_summary`，纯上下文辅助管理员定位，**不参与任何鉴权/决策**。前端会把它展示在弹窗里（透明、可编辑前提示），符合「用户无感知邮箱但知情内容」。

这样既诚实（不假装能从 DB 拿到错误摘要），又达成核心目标（用户不接触邮箱）。

## 3. 后端设计

### 3.1 新增端点

```
POST /api/v1/me/feedback
```

- 鉴权：`CurrentUser`（当前用户视角，与 `/me/favorites` 同前缀语义）。
- 不做 `Idempotency-Key`：响应是固定的 `{submitted: true}`，重发不产生有副作用的状态记录，纯通知邮件。
- **必挂限流**（memory 约定：发邮件端点必须限流）：`check_rate_limit(r, f"rl:feedback:{user.id}:{ip}", settings.default_rate_limit_per_min, 60)`。

### 3.2 请求 / 响应

请求 `FeedbackReq`：

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `run_id` | `str`（UUID） | 是 | 必须是当前用户名下的 run，否则 `GAME_NOT_FOUND` |
| `message` | `str` | 否 | 允许空串；上限 2000 字符，超限返回 `VALIDATION_ERROR`（400，项目统一把 Pydantic 422 转 400） |
| `error_summary` | `str` | 否 | 允许空串；上限 2000 字符 |

响应 `FeedbackResp`：`{ "submitted": true }`，包在 `ApiResponse` 里。

### 3.3 处理流程（`app/feedback/services.py`，新）

`submit_feedback(db, r, user, ip, req) -> FeedbackResp`：

1. `check_rate_limit(...)` —— 同 `auth.register` 模式。
2. `run = await get_run(db, user, UUID(req.run_id))` —— 复用，自带用户归属校验（不存在/非本人 → `GAME_NOT_FOUND`）。
3. `admin_email = await get_admin_contact_email(db)`；解析结果为空字符串 → 抛 `AppError(ErrorCode.INTERNAL, "未配置管理员联系邮箱")`（显式不静默）。
4. 拼邮件：
   - subject = `f"GameForge 反馈 · run {run.id}"`
   - body = 由「用户标识（id）、run_id、阶段（run.phase，如有）、可选错误摘要、用户留言」分段拼成纯文本。
5. `await email_queue.enqueue_notification(admin_email, subject, body)`。
6. 返回 `FeedbackResp(submitted=True)`。

> 不写 `db.commit()`（本端点不修改 DB），不写 `AuditLog`（非 admin 操作；如需留痕属未来扩展，YAGNI）。

### 3.4 文件改动清单（后端）

| 文件 | 改动 |
|---|---|
| `backend/app/schemas/feedback.py` | **新**：`FeedbackReq`、`FeedbackResp` |
| `backend/app/feedback/__init__.py` | **新**：空 |
| `backend/app/feedback/services.py` | **新**：`submit_feedback` |
| `backend/app/api/feedback.py` | **新**：`router = APIRouter(prefix="/me", tags=["feedback"])`，`POST /feedback`，依赖 `user: CurrentUser, db: DbSession, r: RedisClient`，从 `request.client.host` 取 IP |
| `backend/app/main.py` | 加 `app.include_router(feedback.router, prefix=API_V1)`（位置紧随其它 `/me/*` 路由） |
| `backend/tests/test_feedback.py` | **新**：见 §3.5 |
| `contracts/openapi.json` | 重生成（`uv run python -c "from app.export_openapi import export; ..."`，Windows 必须 utf-8 显式写） |

### 3.5 后端测试（`tests/test_feedback.py`）

覆盖：

1. 正常提交（带 message + error_summary）→ 200，`enqueue_notification` 被以正确 `(admin_email, subject, body)` 调用一次，body 含 runId 和留言。
2. `message` 为空 → 仍 200（可空提交）。
3. `run_id` 非本人 → `GAME_NOT_FOUND`，不发邮件。
4. `message` 超 2000 字符 → 422（Pydantic 校验，不进服务层）。
5. 限流触发（连续打满 `default_rate_limit_per_min`）→ `RATE_LIMITED`，且后续请求不发邮件。
6. `get_admin_contact_email` 返回空 → 抛 `INTERNAL`，不发邮件。

`enqueue_notification` 用 monkeypatch 替换为 capture（不依赖真实 broker），与现有 email 测试同模式。限流测试同 `tests/test_idempotency.py` / auth 测试模式。

### 3.6 验证命令

```bash
cd backend && uv run pytest tests/test_feedback.py
cd backend && uv run pytest tests/test_idempotency.py   # 确认限流相关未被破坏
cd backend && uv run ruff check .
# 重生成契约
cd backend && uv run python -c "from app.export_openapi import export; open('../contracts/openapi.json','w',encoding='utf-8',newline='\n').write(export())"
```

## 4. 前端设计

### 4.1 API 客户端（`frontend/src/api/feedback.ts`，新）

- `submitFeedback(body: { runId: string; message?: string; errorSummary?: string }): Promise<void>`
- 后端响应定为 `ApiResponse[FeedbackResp]`（200，非 204），故前端用 `apiRequest<{ submitted: boolean }>('/me/feedback', { method: 'POST', body: { run_id, message, error_summary } })`，返回值忽略。理由：`ApiResponse` 是全项目统一响应壳，与 `/me/favorites` 等同；不特殊走 204。

### 4.2 `FailureRecoveryBar.tsx` 改动（核心）

1. 删除：`supportEmail` 读取（`import.meta.env.VITE_SUPPORT_EMAIL`）、`contactAdmin` 里的 `mailto:` 拼接逻辑、`Mail` 图标导入如不再用可留（弹窗触发器仍用 Mail 图标）。
2. 新增状态：`const [feedbackOpen, setFeedbackOpen] = useState(false)`。
3. `contactAdmin()` 改为 `setFeedbackOpen(true)`（保留 `copyRunId()` 那一次拷贝，作为副作用——见 §4.4 取舍）。
4. 新增自研 Modal（参考项目内 `ConfirmModal` / `PublishNoteModal` 的自研实现模式）：
   - 标题：`t("feedbackTitle")`（如「反馈给管理员」）。
   - 一个 `<textarea>`，placeholder `t("feedbackPlaceholder")`（「您本次想要反馈什么内容（选填）」），受控，默认空，maxLength 2000。
   - 底部：「取消」+「发送」（用 `Button`，与现有恢复条按钮同尺寸风格）。
   - 「发送」调 `submitFeedback({ runId, message, errorSummary })`：
     - 成功 → 关闭弹窗 + toast `t("feedbackSent")`（「反馈已提交，我们会尽快查看」）+ 清空输入。
     - 失败 → toast `t("feedbackFailed")`，弹窗保持打开，输入保留。
     - 请求 in-flight 时「发送」按钮 `disabled` + `Loader2` 旋转，防重复点击（与后端限流双保险）。
5. Modal 挂在 `<section>` 内末尾（自研 Modal 通常是 portal/条件渲染）。

### 4.3 i18n（`frontend/src/i18n/messages.ts`，中英两份）

新增 key：

| key | zh | en |
|---|---|---|
| `feedbackTitle` | 反馈给管理员 | Send feedback |
| `feedbackPlaceholder` | 您本次想要反馈什么内容（选填） | What went wrong this time? (optional) |
| `feedbackSend` | 发送 | Send |
| `feedbackCancel` | 取消 | Cancel |
| `feedbackSent` | 反馈已提交，我们会尽快查看 | Feedback submitted. We'll take a look shortly. |
| `feedbackFailed` | 反馈发送失败，请稍后重试 | Failed to send feedback. Please try again later. |

`failureContact`（「联系管理员」）文案保留为按钮文字不变。

### 4.4 取舍记录

- **保留 `copyRunId()` 副作用**：当前点击会先把 runId 拷到剪贴板。改造后是否保留？保留——它是独立便利功能，与新弹窗无冲突；但点击语义已从「发邮件」变为「打开反馈弹窗」，拷贝 runId 仍是合理附带。如实现中发现突兀（弹窗一开就改剪贴板），则在计划阶段再定夺。
- **errorSummary 是否在弹窗展示给用户**：默认**不在弹窗里展示**（弹窗只有一个纯输入框，最贴合「无感知」）；但作为隐藏字段随请求发送。如需透明化，可在 placeholder 下加一行小字「将附带本次 run ({runId}) 信息」，作为可选增强。

## 5. 数据流

```
用户点「联系管理员」(FailureRecoveryBar)
  → 打开自研 Modal（单个 textarea）
  → 用户填/不填 → 点「发送」
  → POST /api/v1/me/feedback  { run_id, message, error_summary }
        ├─ check_rate_limit(rl:feedback:{user}:{ip})
        ├─ get_run(db, user, run_id)   # 归属校验
        ├─ get_admin_contact_email(db) # 解析收件人
        ├─ enqueue_notification(admin_email, subject, body)  # 入 RabbitMQ
        └─ 返回 { submitted: true }
  → 前端 toast「反馈已提交」并关弹窗
  → (异步) email worker 消费 → aiosmtplib.send → 管理员收件箱
```

## 6. 错误处理

| 场景 | 行为 |
|---|---|
| 限流超限 | 后端 `RATE_LIMITED`（429），前端 toast `feedbackFailed` |
| run 非本人/不存在 | 后端 `GAME_NOT_FOUND`（404），前端 toast `feedbackFailed` |
| 管理员邮箱未配置 | 后端 `INTERNAL`（500），前端 toast `feedbackFailed` |
| message 超长 | Pydantic 校验 → `VALIDATION_ERROR`（400），前端表单层用 maxLength 拦截，理论不触达 |
| 网络失败/worker 投递失败 | `enqueue_notification` 失败由 broker at-least-once 重投；API 层不阻塞用户，先返回成功（邮件 worker 兜底） |

## 7. 测试策略

- 后端：`tests/test_feedback.py`（§3.5），核心是 mock `enqueue_notification` 断言调用参数 + 限流。
- 前端：`FailureRecoveryBar` 现有无单测；本次改动以手动验证 + 类型检查为主（`pnpm build` / `pnpm test` 如有相关组件测则跑）。前端不强求新增组件单测（YAGNI，与项目现状一致），如实现成本低则补一个「点击发送 → 调用 API → toast」的基础用例。

## 8. 不做（YAGNI）

- 不做常驻/全局反馈入口。
- 不做反馈历史落库 / 管理后台反馈列表。
- 不做富文本/附件反馈。
- 不引入新邮件任务类型（复用 `TASK_SEND_NOTIFICATION`）。
- 不新增 settings 配置项（复用 `ADMIN_CONTACT_EMAIL`）。
- 不做 `Idempotency-Key`（纯通知邮件，无状态副作用）。
