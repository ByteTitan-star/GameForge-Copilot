# 联调状态看板

> 前端 agent 维护。记录每个端点 mock→real 切换状态，后端据此知联调进度。
> 状态：`mock` / `real` / `blocked`
>
> **2026-08-07**：前端补齐 Admin 审批闭环、真 WS 客户端、托管 URL、401 refresh、`base_url`、HITL modify。
> 续：Forge 进页恢复未结束 run + WS 重连、邮箱验证/重置 `?token=` 深链、未验证登录引导 Setting、
> Admin「已发布」Tab、WS `usage` 配额提示、ChatPanel 流式光标。
> 再续：`/reset-password` 对齐邮件、`PATCH admin/users` 日配额覆盖 UI、`GET /me/llm-configs/models`、
> QUOTA/EMAIL 错误引导文案。
> **2026-08-07 续**：`POST /auth/password/change` 已出契约；Setting 页内改密表单；AdminUserItem 回显
> `daily_token_limit`；`/forgot-password` 与 `/reset-password` 双路由可用。
> **2026-08-07 前端去 Mock**：已删除 MSW；默认直连 `VITE_API_BASE_URL`。冒烟：`pnpm smoke:real`。

## M1 认证

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /auth/register | real | |
| POST /auth/verify-email | real | Worker `[dev-email]` |
| POST /auth/login | real | |
| POST /auth/refresh | real | client 401 自动 refresh |
| POST /auth/logout | real | 204 |
| POST /auth/password/reset | real | |
| POST /auth/password/reset/confirm | real | `/reset-password?token=` |
| POST /auth/password/change | real | Setting 登录态改密 |

## M2 LLM 配置

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /me/llm-configs | mock→可 real | 含 `base_url` |
| POST /me/llm-configs | mock→可 real | openai_compat 必填 base_url |
| PATCH /me/llm-configs/{id} | mock→可 real | |
| DELETE /me/llm-configs/{id} | mock→可 real | |
| POST /me/llm-configs/{id}/test | mock→可 real | |
| GET /me/llm-configs/models | mock→可 real | Setting 模型 datalist；后端 Redis 缓存 |

## M3 用量

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /me/usage | mock→可 real | |
| GET /me/notifications | mock→可 real | 侧栏铃铛；审批结果站内信 |
| POST /me/notifications/{id}/read | mock→可 real | |

## M4 游戏生成骨架

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /games | mock→可 real | |
| GET /games | mock→可 real | PaginatedData |
| GET /games/{id} | mock→可 real | |
| PATCH /games/{id} | mock→可 real | 草稿重命名（GameCard） |
| DELETE /games/{id} | mock→可 real | |
| POST /games/{id}/runs | mock→可 real | 多轮 = 同 game 新 run + requirement |
| GET /games/{id}/runs | mock→可 real | |
| GET /games/{id}/versions | mock→可 real | |
| GET /runs/{run_id} | mock→可 real | HITL 后 status=`paused` |
| POST /runs/{run_id}/pause | mock→可 real | Forge 顶栏 |
| POST /runs/{run_id}/resume | mock→可 real | Forge 顶栏 |
| POST /runs/{run_id}/cancel | mock→可 real | Forge 顶栏 |
| WS /ws/runs/{run_id} | mock→可 real | `src/ws/client.ts` |

## M5 沙箱与托管

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /play/{slug} | mock→可 real | 长 Cache-Control |
| GET /draft/{game_id}/{version} | mock→可 real | 私有短缓存；GamePlayer Bearer→blob |

## M6 全生成链

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /games/{id}/runs/{run_id}/hitl/resolve | mock→可 real | approve / modify；节点含 plan/sandbox/qa |

## M7 发布审批

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /games/{id}/publish/submit | mock→可 real | GameCard + Forge 顶栏 |
| GET /publish/queue | mock→可 real | Admin 审批工作台 |
| POST /publish/{id}/approve | mock→可 real | |
| POST /publish/{id}/reject | mock→可 real | |
| POST /games/{id}/take-down | mock→可 real | Admin「已发布」区 |

## M8 管理后台余下

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /admin/usage | mock→可 real | |
| GET /admin/users | mock→可 real | 含 `daily_token_limit` 回显 |
| PATCH /admin/users/{id} | mock→可 real | 角色/禁用/`daily_token_limit` |
| GET /admin/games | mock→可 real | Admin「已发布」Tab |
| GET /admin/audit-logs | mock→可 real | Admin「审计」Tab |
| GET /admin/settings | mock→可 real | 含月配额 |
| PUT /admin/settings | mock→可 real | daily / monthly / rate |

## 健康检查

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /healthz | optional | 前端业务不依赖 |
| GET /ready | optional | 运维探针 |
| GET /metrics | optional | Prometheus |

## 环境变量

```bash
# frontend/.env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
# 可选：VITE_HOSTING_BASE_URL / VITE_WS_BASE_URL（默认从 API 根推导）
```

## docs/01 MVP 运维项（非联调阻塞）

| 项 | 说明 |
|---|---|
| CSRF | Bearer 模式（docs/06）；不走 cookie session，无额外 CSRF token |
| 备份 | `scripts/backup-pg.sh` + docs/09；部署侧 cron |
