# 02 · 整体架构

## 设计原则

- **编排与领域分离**：LangGraph 只管状态流转/检查点/HITL/流式；游戏生成的领域知识（skill/prompt、产物构建、托管、审批、计量）是项目自己的资产，不混进编排图。
- **LLM 无关**：后端 `llm/` 抽象一层 provider，按用户 Web 端配置动态构造客户端，系统不绑死任何厂商、不持有默认 key 的硬依赖。
- **生产级优先**：async IO、加密、限流、可观测、可恢复，不做 demo 级实现。
- **玩法零硬编码**：业务代码不约束具体游戏逻辑，玩法完全由 Agent 生成。

## 分层

```
┌──────────────────────────────────────────────────────┐
│  前端  React + Vite + TS                              │
│  设计对话 / 试玩页 / 管理后台 / Setting            │
└───────────────┬──────────────────────────────────────┘
                │ HTTP (REST) + WS（生成流式）
┌───────────────▼──────────────────────────────────────┐
│  API 层  FastAPI                                      │
│  路由 / 鉴权 / 限流 / WS 事件推送                    │
└───┬───────┬────────┬───────────┬────────────┬───────┘
    │       │        │           │            │
┌───▼──┐ ┌──▼───┐ ┌──▼────┐ ┌────▼────┐ ┌────▼────┐
│ forge│ │auth  │ │hosting│ │ publish │ │ usage   │
│ 编排 │ │认证  │ │ 托管  │ │ 审批流  │ │ 计量    │
└──┬───┘ └──────┘ └───┬───┘ └─────────┘ └────┬────┘
   │                    │                     │
┌──▼──────────────┐  ┌──▼──────┐        ┌────▼────┐
│ LangGraph 状态图 │  │ 对象存储 │        │  Redis  │
│ ├ 策划子图       │  │ /静态目录│        │ 用量/会话│
│ ├ 美术子图       │  └─────────┘        │ /限流   │
│ ├ 代码子图─▶沙箱 │                     └─────────┘
│ └ 质检子图       │
└──┬──────────────┘
   │
┌──▼──────────────┐
│ llm provider 抽象│ ◀─ 用户 Web 配置（apikey/model）
│ (Anthropic/OpenAI)│
└──────────────────┘

┌──────────────────────────────────┐
│ PostgreSQL  用户/游戏/发布/审计 │
└──────────────────────────────────┘
```

## 组件职责

### forge（游戏生成编排）
- `forge/graph.py`：主状态图，编排子图调用顺序与检查点。
- `forge/subgraphs/`：策划、美术、代码、质检四个子图，各含节点与工具集。
- `forge/sandbox.py`：封装 execute_code 沙箱，代码子图在沙箱内生成+构建+自测。
- `forge/skills/`：生成 skill 与 prompt 体系（非玩法约束，是生成方法论）。
- 检查点存 Redis，长任务可中断/恢复。
- HITL：策划稿确认、发布前自检等节点中断等待用户/管理员。

### llm（provider 抽象）
- 按 `user.llm_config`（provider/model/apikey）构造客户端。
- 统一返回 `(content, usage)`，`usage` 含 input/output tokens。
- 不缓存 key 明文，运行时解密使用。

### hosting（产物托管）
- 沙箱构建产物（HTML/JS/CSS/资源）落对象存储或本地静态目录。
- 按 `game.slug` + 版本号寻址，`/play/{slug}` 路由到对应产物。

### publish（发布审批）
- 状态机：draft → submitted → reviewing → approved(published) / rejected → taken_down。
- 管理员工作台操作审批/上下架。

### usage（用量计量）
- 每次 LLM 调用后取 `usage`，按 user_id 累计 Redis（日/月/总量）。
- 配额/限流查询 Redis 实时判断。
- 不做估算，只用真实 usage。

### auth（认证）
- 邮箱注册+验证、JWT、角色（user/admin）。详见 [06-auth-and-security.md](06-auth-and-security.md)。

## 数据流：一次游戏生成的完整链路

1. 前端建 WS，用户输入"设计一个贪吃蛇"。
2. API 鉴权 → 创建 `game` 记录（draft）与 `generation_run`。
3. forge 启动 LangGraph，加载用户 LLM 配置构造客户端。
4. 策划子图：产出设计稿（玩法/界面/关卡），HITL 等用户确认。
5. 美术子图：产出素材（或复用资源库）。
6. 代码子图：在沙箱内生成代码 → 构建 → 自测；失败回退修正。
7. 质检子图：试玩校验，产出质检报告。
8. 产物落 hosting，绑定 slug 与版本。
9. 全程每次 LLM 调用写 usage 到 Redis；事件经 WS 推前端。
10. 生成完成，前端展示试玩页。用户可迭代或提交发布。

## 技术选型理由

| 决策 | 理由 |
|---|---|
| LangGraph 而非自研 loop | checkpoint/HITL/subgraph/流式开箱即用，避免重造轮子（DRY）与生产稳定性风险 |
| LangGraph 而非 Claude Agent SDK | SDK 会让项目空心化；LangGraph LLM 无关，Claude 仅作可换 provider |
| Python + FastAPI | 与沙箱资产同栈；async 契合 IO 密集；uv 管理规范 |
| React + Vite | 轻量、便于嵌入游戏静态产物、生态大 |
| PostgreSQL + Redis | 关系主数据 + 高频计量/会话/限流/检查点，职责清晰 |
| 用户自带 key | 不绑死厂商、不经手计费、满足多 provider 需求 |

## 可观测

- 生成全链路 trace（节点/工具/LLM 调用/prompt/响应）上报 langfuse Cloud，供回看与调试。
- LangGraph 经 langfuse callback 集成自动上报，无需手写埋点。
- 实时进度经 WS 推前端（见 [03](03-game-generation.md)），与 langfuse 事后可观测正交。
- 配额限流仍走 Redis usage 实时值（见 [05](05-tenant-usage-llm.md)），不依赖 langfuse。
- 注意：prompt 与生成内容上报到 langfuse Cloud（第三方域名），属出域数据，上线前需合规确认。

## 不做

- 不自研 agent loop、不画自己的多智能体编排图。
- 不在业务代码硬编码任何游戏玩法/规则。
- 不持有/不默认使用系统级 LLM key 作为唯一来源。
