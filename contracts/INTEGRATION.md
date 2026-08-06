# 联调状态看板

> 前端 agent 维护。记录每个端点 mock→real 切换状态，后端据此知联调进度。
> 状态：`mock` / `real` / `blocked`
>
> 2026-08-06：M0 过渡类型 + MSW 全量 handler 已就绪；`openapi.json` 仍为空 paths，类型暂手写于 `frontend/src/api/types.gen.ts`。后端提交真实 openapi 后前端将 `pnpm gen:api` 覆盖并据 CHANGELOG 调整。

## M1 认证

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /auth/register | mock | MSW |
| POST /auth/verify-email | mock | MSW；mock token=`123456` 或邮箱本身 |
| POST /auth/login | mock | MSW；demo@gameforge.dev / password123 |
| POST /auth/refresh | mock | MSW rotation |
| POST /auth/logout | mock | MSW |
| POST /auth/password/reset | mock | MSW；防枚举恒返回 sent |
| POST /auth/password/reset/confirm | mock | MSW；重置码 654321 |

## M2 LLM 配置

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /me/llm-configs | mock | MSW |
| POST /me/llm-configs | mock | MSW；保存前 mock 连通测试 |
| PATCH /me/llm-configs/{id} | mock | MSW |
| DELETE /me/llm-configs/{id} | mock | MSW；默认配置不可删 |
| POST /me/llm-configs/{id}/test | mock | MSW |

## M3 用量

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /me/usage | mock | MSW；Setting 用量看板 + UsageChart（Noto Sans SC） |

## M4 游戏生成骨架

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /games | mock | MSW |
| GET /games | mock | MSW |
| GET /games/{id} | mock | MSW |
| DELETE /games/{id} | mock | MSW |
| POST /games/{id}/runs | mock | MSW |
| GET /games/{id}/runs | mock | MSW |
| GET /games/{id}/versions | mock | MSW |
| GET /runs/{run_id} | mock | MSW |
| WS /ws/runs/{run_id} | mock | `src/ws/mock.ts` 时间线回放（非真实 WS 套接字） |

## M5 沙箱与托管

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /play/{slug} | mock | 前端路由 + mock-play.html |
| GET /draft/{game_id}/{version} | mock | 前端路由 + mock-play.html |

## M6 全生成链

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /games/{id}/runs/{run_id}/hitl/resolve | mock | MSW；路径含 run_id（对齐 docs/10 §5） |

## M7 发布审批

| 端点 | 状态 | 备注 |
|---|---|---|
| POST /games/{id}/publish/submit | mock | MSW |
| GET /publish/queue | mock | MSW admin |
| POST /publish/{id}/approve | mock | MSW admin |
| POST /publish/{id}/reject | mock | MSW admin |
| POST /games/{id}/take-down | mock | MSW admin |

## M8 管理后台余下

| 端点 | 状态 | 备注 |
|---|---|---|
| GET /admin/usage | mock | MSW admin |
| GET /admin/users | mock | blocked: openapi/docs/10 未给出精确 schema |
| PATCH /admin/users/{id} | mock | blocked: openapi/docs/10 未给出精确 schema |
| GET /admin/settings | mock | blocked: openapi/docs/10 未给出精确 schema |
| PUT /admin/settings | mock | blocked: openapi/docs/10 未给出精确 schema |
