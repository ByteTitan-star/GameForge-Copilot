# ADR-12: API, Frontend & Ops Debt

* Status: **Accepted**（Section A/B/C 一并 Accept；实施仍可分批）
* Date: 2026-08-16
* Accepted-by: ByteTitan-star
* Related: P1-24～26；P2-5, P2-8～11, P2-13～20, P2-24～30；[ADR-MODIFICATION-GUIDE-2026-08-16.md](./ADR-MODIFICATION-GUIDE-2026-08-16.md)

---

## Context

审查后半段为 API 幂等/校验/分页、前端 Forge/WS/鉴权体验、运维资源与观测债务。单项多为 P2，但 **P1-24/25/26** 会直接造成错游戏操作、假失败、误登出，应优先于一般 P2。

**核实：** Forge 切游戏不重置、WS 闭包旧 token、`fetchDraftHtml` 自刷新——属实。其余 P2 按机制归类，实施前 spot-check。

## Decision

本 ADR 分三节独立 Accept，避免「一纸绑死全部债务」。

### Section A — 前端高优先级（P1-24/25/26）【建议随批次 B】

1. `routeGameId` 变化时重置全部 run 相关 state，或 `ForgePage` 使用 `key={gameId}` 强制重挂载。
2. WS 重连从 auth store **重读**最新 access token；4401 时先 refresh 再重试；增加应用层心跳。
3. `fetchDraftHtml` 必须走与 `client.ts` 相同的 single-flight refresh，禁止并发 refresh 清会话。

### Section B — API 契约（P2-8～13）【排期】

1. 建状态端点补齐幂等五件套（对照 `create_run`）：`Idempotency-Key` / 创建锁 / 部分唯一索引 / 限流；`fork` 至少幂等键。
2. 先查后写统一捕获 `IntegrityError` → 409 或幂等成功（reactions / handle / preferences）。
3. Pydantic 补 `max_length` / `ge`；`feedback.run_id` 用 UUID 类型。
4. 列表接口补分页（game runs、publish queue 历史等）。
5. 限流键：统一可信代理下的客户端 IP 策略，并加账号维度；禁止反代后全站共享一个桶。

### Section C — 运维 / 观测 / 其余前端（P2-5, 14～20, 24～30）【排期】

1. **LLM provider：** 厂商差异走 profile，禁止主干硬编码域名/模型子串；usage 缺帧记 0 + 告警，**禁止字符估算**（对齐 CLAUDE.md）。
2. **Outbox / scheduler：** 已发布行定时清理；cancel 下推谓词；scheduler `FOR UPDATE SKIP LOCKED` + per-row try/except。
3. **RabbitWsBus：** 复用长生命周期 channel；exchange declare 缓存。
4. **同步 IO：** `rmtree` / `copytree` / chmod 扫描等挪 `asyncio.to_thread`，避免卡住租约心跳。
5. **Lifespan：** `engine.dispose()` + Redis pool `aclose()`。
6. **Metrics：** `/preview/{token}`、`/play/{slug}` 按路由模板归一化 label。
7. **Analytics：** `play_count` 原子自增；UV 不依赖可伪造 XFF。
8. **图状态：** `_qa_html` 等大字段禁止无白名单并入主图 state（P2-24）。
9. **前端体验：** 轮询 deps 用原始值；messages 上限；run 状态收敛 react-query；ChatPanel 滚动跟随。
10. **Token 存储：** refresh 迁 httpOnly cookie + 会话族检测；WS 改首帧鉴权或短期票据（可单独安全子节）。

## Consequences

* Section A 显著降低工坊误操作与「假失败」。
* Section B/C 降低 500、DoS 限流误伤、连接泄漏与报表失真。
* 分节 Accept 允许 Owner 只签字 A，其余保持 Proposed。

## Non-goals

* 一次性重写全部前端状态管理框架。
* 在本 ADR 内重新定义产品配额数值（配额强制策略见 ADR-07）。
