# 06 · 认证与权限

## 注册与邮箱验证

- 注册：邮箱 + 密码。邮箱唯一，密码用 `argon2` 哈希存储。
- 验证：注册后发验证邮件（异步队列，禁止同步阻塞），用户点链接激活。
  - 验证 token 签发短期 JWT 或随机 token 落 `email_verification` 表，过期作废。
- 未验证账号可登录但仅能进 setting 配置 LLM，不能发起 generation_run。

## 登录与会话

- 登录：邮箱 + 密码，校验通过签发 `access_token`（短期 JWT）+ `refresh_token`（长期，落 Redis 可撤销）。
- access 失效用 refresh 轮换：旧 refresh 立即失效，签发新对（rotation）。
- 登出：refresh 从 Redis 删除，access 自然过期。
- 密码重置：邮箱发重置链接，token 单次有效，落 `password_reset_tokens` 表（过期/已用即失效）。

## 鉴权中间件

- FastAPI 依赖注入 `current_user`，从 access_token 解析 `user_id` + `role`。
- 路由按角色守卫：`require_user` / `require_admin`。
- WS 鉴权：浏览器原生 WebSocket 不能设自定义头，token 经查询参数 `?token=<access_token>` 传递，握手校验，失败拒接；access 过期则服务端关闭，前端 refresh 后重连。
- 注册接口同样限流（防滥用），Redis key `rl:register:{ip}`。

## 权限模型

| 角色 | 数据权限 |
|---|---|
| user | 仅自己的草稿/配置/用量；可提交发布；试玩自己的游戏 |
| admin | 用户管理 + 已发布游戏上下架 + 审批 + 系统用量 + 全局设置 |
| 任何人 | 访问已 published 的 `/play/{slug}`（无需登录） |

### 可见性约束（强制）
- 查询草稿/游戏记录时按 `owner_id = current_user.id` 过滤，**admin 也不能绕过**查 draft（admin 只能从审批队列见 submitted/reviewing）。
- 这在数据访问层强制，不靠应用层自觉。

## 安全措施

| 项 | 措施 |
|---|---|
| 密码 | argon2 哈希 |
| LLM apikey | 服务端加密（`Fernet`/KMS），明文不落库不落日志 |
| token | JWT 短 access + Redis refresh rotation |
| 限流 | 网关层 + 用户级（登录、注册、LLM 调用） |
| CORS | 白名单来源 |
| CSRF | cookie 模式下加 SameSite + token；首选用 Bearer 头 |
| 输入校验 | Pydantic schema 校验所有入参，不信任外部输入 |
| 邮箱验证 | 注册必验证 |
| 审计 | 管理员操作（审批/下架/配额调整/用户禁用）全落日志 |
| 沙箱 | 生成期代码受限沙箱，无网络、资源分级 |

## 邮件

- 邮件发送走异步任务队列（IO 密集，历史教训：禁止同步阻塞）。
- 验证邮件、重置邮件、审批结果通知、下架通知、配额告警。
- SMTP 配置走环境变量，不硬编码。

## 错误处理

- 鉴权失败：统一 401，不泄露用户是否存在。
- 权限不足：403。
- 显式错误响应，禁止静默吞异常。
