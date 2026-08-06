# 05 · 多租户、用量计量与 LLM 配置

## 多租户模型

- 单实例多租户：所有用户共享同一部署，数据按 `user_id` 隔离。
- 无租户概念（不搞组织/团队层），最简：用户 + 管理员两角色。
- 进阶：组织/团队协作留到后续，YAGNI。

## 角色与权限

| 角色 | 权限 |
|---|---|
| user | 管理自己的草稿/LLM 配置/用量；提交发布；试玩自己的游戏 |
| admin | 用户管理 + 已发布游戏上下架 + 审批 + 系统用量监控 + 全局设置 |

> 草稿对所有非创建者（含 admin）不可见；admin 只在审批队列见 submitted/reviewing。详见 [06-auth-and-security.md](06-auth-and-security.md)。

## LLM Provider 配置（用户自带 Key）

### 存储
- 用户在 Web setting 提交：`provider`（anthropic/openai/兼容）、`model`、`apikey`。
- apikey 服务端加密（`Fernet`/KMS）落 PostgreSQL `user_llm_config.apikey_enc`，前端只存掩码。
- 一用户可存多组配置，指定 `is_default`。

### 使用
- 每次 generation_run 取用户默认配置（或 run 指定配置），运行时解密构造 provider 客户端。
- 解密后的明文 key 仅在内存、单次调用生命周期内，不落日志、不进 trace。

### 连通性测试
- 保存配置时发一次最小请求（如 1 token），失败则不让保存并提示原因。

### 模型列表来源
- 按 provider 调用其 `/models` 端点（Anthropic/OpenAI 均支持）拉取可选模型，短期缓存。
- 拉取失败时回退到配置白名单（按 provider 预置常用模型）。
- 不把硬编码列表作唯一来源，避免模型更新过期。

## token 用量计量

### 数据来源
- **只用 LLM 响应里的真实 `usage`**（`input_tokens`/`output_tokens`），不估算、不靠本地 tokenizer 猜。
- Anthropic、OpenAI 及兼容厂商的响应均含 usage；`llm/` 抽象层统一提取并返回。

### 计量存储（Redis）

| Key | 类型 | 内容 |
|---|---|---|
| `usage:user:{uid}:day:{date}` | hash | input_tokens / output_tokens / calls |
| `usage:user:{uid}:month:{ym}` | hash | 同上 |
| `usage:user:{uid}:total` | hash | 累计 |
| `usage:sys:day:{date}` | hash | 系统每日总量 |
| `usage:sys:month:{ym}` | hash | 系统月总量 |
| `usage:sys:total` | hash | 系统累计 |

- 每次 LLM 调用结束（成功或失败但已产生 usage）即 `HINCRBY` 累加。
- 月总量按自然日滚动，月初自动切 key。

### 配额与限流

| 维度 | 实现 |
|---|---|
| 每用户日 token 上限 | 配额默认值（admin 全局设置可调）+ 用户级覆盖；run 前查 Redis 判断，超限挂起 |
| 每用户调用频率 | 滑动窗口限流（Redis ZSET 或令牌桶） |
| 并发 run 数 | 每用户同时进行中的 generation_run 上限 |
| 系统总量告警 | 阈值触发通知 admin |

- 配额耗尽：run 挂起，提示用户；不静默失败。
- admin 可在后台看系统总量 + 每用户用量，并可调整用户配额。

### 成本估算（进阶）
- 按 provider 公开单价 × token 数给出估算视图，仅供参考（实际计费走用户自己的 key）。

## 与计费的关系

- **系统不经手任何 LLM 计费**：调用走用户自带 key，钱结在用户与厂商之间。
- 系统只统计 token 消耗与调用次数，用于配额限流与容量管理，与钱无关。
- 这条消除"自带 key vs 管理员统计用量"的矛盾——统计靠响应 usage，与谁付钱解耦。
