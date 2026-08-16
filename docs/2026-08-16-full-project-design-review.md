# 全项目设计审查报告（2026-08-16）

> 审查方式：11 个独立视角（超时配置 / sandbox 生命周期 / worker 并发 / API 设计 / 资源泄漏 / LangGraph 编排 / 前端架构 / 安全 / 复用与效率 / CLAUDE.md 约定 / 架构层次 + 补漏）并行扫描，关键发现均已在源码逐行核实。
> 本报告只记录问题与修复建议，不含代码改动。
> 严重度：P0 = 安全/致命故障，应立即处理；P1 = 高概率生产事故或明确攻击面；P2 = 设计债务，择机偿还。

---

## P0 — 立即处理

### P0-1 JWT 密钥硬编码默认值，无生产环境 fail-fast 校验

- **位置**：`backend/app/core/config.py:17`；派生影响 `backend/app/auth/security.py:39`、`backend/app/core/crypto.py:23-27`
- **问题**：`jwt_secret: str = "dev-secret-change-me-to-a-32-byte-random-string"`。全仓库无 `env != development` 时的非默认值断言。对比：`llm_apikey_encryption_key` / `s3_sk` 缺省会显式失败，唯独 jwt_secret 有可用默认值。
- **触发→后果**：部署时漏配 `JWT_SECRET` → 服务照常启动 → 任何读过源码的人可对任意 user_id 签发 access token（含 admin，`require_admin` 只查 DB role）→ 全量账号接管。同一密钥还经 HKDF 派生 Fernet key 解密用户 LLM apikey，DB 泄露时 key 全部可解。
- **建议**：启动时若 `env != development` 且 `jwt_secret` 为默认值/长度 < 32，直接拒绝启动。

### P0-2 LLM source_files 可覆盖平台 manifest → 依赖白名单失效；Windows 本地 builder 存在命令注入 RCE

- **位置**：`backend/app/forge/build/manifest.py:124`；`backend/app/sandbox/builder.py:92-95, 269`
- **问题**：`merge_workspace` 用 `workspace.update(source_files)` 无文件名白名单，LLM 输出的 `package.json` / `pnpm-workspace.yaml` / `vite.config.ts` 可直接覆盖平台生成的版本锁定与 allowBuilds 硬约束。且 `corepack_activate_shell` 把 `package.json#packageManager` 字段拼进 shell 字符串后由 `create_subprocess_shell` 执行。
- **触发→后果**：LLM（或诱导 LLM 的输入）输出恶意 `package.json` → prepare 阶段（`network=bridge`）拉任意 npm 包执行 postinstall；在 `builder_backend=local` 的 Windows 宿主上，`packageManager` 内容直接变成宿主机任意命令执行。
- **建议**：① `merge_workspace` 对 `source_files` 加保留文件名黑名单（manifest 三件套不可覆盖）；② `packageManager` 用正则白名单 `^pnpm@\d+(\.\d+)*$` 校验后拼接。

### P0-3 worker 容器无 restart 策略，任何未捕获异常即永久停摆

- **位置**：`docker-compose.yml:78`（worker 服务无 `restart:`；backend 服务同样没有）
- **问题**：`worker.py` 的 `main()` 中 `_consume()` 抛任何异常（连接失败、消费循环崩溃）进程即退出，容器不重启。
- **触发→后果**：worker 一次崩溃 → execute_run / resume_run / 验证码邮件 / 找回密码邮件 / outbox 派发循环全部中断且无人恢复 → run 永久卡 RUNNING、注册收不到验证码，直到人工介入。
- **建议**：worker 与 backend 服务加 `restart: unless-stopped`；同时给 `_consume()` 加外层异常捕获 + 重连退避。

### P0-4 基础设施客户端全无底层超时 + done 节点无 TimeoutPolicy → worker 静默挂死（"worker 死锁"实态）

- **位置**：`backend/app/core/db.py:7`（asyncpg 无 statement/pool timeout）、`backend/app/core/redis.py:7`（无 socket_timeout）、`backend/app/sandbox/docker.py:122-128`（aiodocker/aiohttp 默认 total=None、`images.pull` 无 wait_for）、`backend/app/forge/graph.py:1234`（`done` 节点是唯一未挂 TimeoutPolicy 的节点）
- **问题**：任何一条挂起的 IO（Postgres 行锁等待、Redis 半开连接、Docker daemon 假死时的 `container.delete`）都会让协程永久 await。节点级 TimeoutPolicy 能杀图内节点，但取消后在 finally 里执行的 `container.delete(force=True)` 又是一个无超时 await；收尾 commit/publish、done 节点均在策略之外。
- **触发→后果**：3 个挂起 IO（`max_concurrent_tasks=3`）各占满一个 prefetch 槽位 → 消息不 ack、租约心跳照常续（Redis 正常时）→ broker 不重投、worker 静默停摆，只能人工重启。这正是"worker 是否死锁"的答案：不是经典互斥死锁，而是**无超时 IO 永久占用并发槽位的活锁**。
- **建议**：① asyncpg `connect_args={"timeout": ..., "command_timeout": ...}`；② redis `socket_timeout`/`socket_connect_timeout`；③ aiodocker 全部调用包 `asyncio.wait_for`；④ done 节点也挂 policy；⑤ 收尾/清理路径统一走带超时包装。

---

## P1 — 高优先级（可靠性）

### P1-1 ack 后置于整个 run，与 RabbitMQ consumer_timeout 必然冲突

- **位置**：`backend/app/messaging/worker.py:192`（`async with message.process(requeue=False)` 包住整个 run）；`backend/app/forge/reliability/policy.py:47-55`（code_qa 外墙 ≈ 2520s）；`docker-compose.yml` rabbitmq 未配 `consumer_timeout`（默认 30 分钟）
- **触发→后果**：一个正常慢 run 超 30 分钟未 ack → broker 以 PRECONDITION_FAILED 关闭整个 channel → 该 channel 上全部 prefetch 消息批量重投；原任务跑完后 ack 落空（异常被 `gather(return_exceptions=True)` 吞掉），消费循环退出 → 与 P1-3 重投热循环叠加，大规模重复执行。
- **建议**：rabbitmq 显式配 `consumer_timeout` ≥ 最大 run 预算，或改用"执行租约 + 快速 ack + 独立看门狗"模式。

### P1-2 decode 失败与 DLQ/重投发布自身失败 → 消息静默丢失，不落 DLQ

- **位置**：`backend/app/messaging/worker.py:193`（`decode_task` 在 try 块外）、`worker.py:220-232`（`_republish_task`/`_publish_to_dlq` 无兜底 try）
- **触发→后果**：① 消息体非法 → `async with message.process(requeue=False)` 退出时 reject 丢弃，任务异常无人 await（只有 GC 时的 "Task exception was never retrieved"）；② 处理失败进 except 后发布到 DLQ/重投时 broker 瞬时故障 → 同样 reject 丢弃。execute_run 消息丢失后 run 永久卡 RUNNING（48h 回收只针对 PAUSED）。
- **建议**：decode 与发布动作全部纳入 try/except + 显式日志；DLQ 发布失败时降级本地落盘。

### P1-3 TaskLeaseBusy 固定 sleep(2) 原计数无限重投 → 0.5Hz 热循环

- **位置**：`backend/app/messaging/worker.py:208`（已核实：`await asyncio.sleep(2)` + `_republish_task(retry_count=retry)` 不递增）
- **触发→后果**：at-least-once 重投的重复 execute_run 在原 run 正常执行期间（可达 40+ 分钟）每 2 秒被 republish 一次，可能仍落回同一 worker → 上千次无意义 publish/消费/日志，RabbitMQ 与日志刷爆；`worker_max_redeliveries=5` 对该路径完全不生效。
- **建议**：busy 路径改为延迟重投（x-delay 或记录首次时间戳做上限），或递增 retry 计数 + 指数退避。

### P1-4 worker 崩溃后重投不读 checkpoint，从 plan 整图重跑 → 重复计费

- **位置**：`backend/app/forge/graph.py:1299-1300`（`duplicate_execute = not resume and run.status != RUNNING`；崩溃时 status 恰好还是 RUNNING → 放行）、`graph.py:1453`（只有 `resume=True` 才 load_state）
- **触发→后果**：run 跑到 code 阶段时 worker 被 OOM kill → 消息重投 → 守卫放行 → `_run_body(resume=False)` 从 plan 重新生成 → 用户 token 配额被重复扣、API 成本翻倍；side_effect 幂等键含 execution_id，重跑是新 execution，幂等层拦不住。
- **建议**：重投消息带 `redelivered` 标志时强制走 checkpoint 恢复路径；或对非 resume 启动也先 `load_state` 检查已有进度。

### P1-5 promote 幂等标记先置位后提交 → 提交失败后重放永久跳过 promote，DONE 但交付旧版本

- **位置**：`backend/app/forge/graph.py:1175-1182`（已核实：`try_begin_side_effect` 成功 → `promote_candidate` → `ctx.s.commit()`；失败路径 commit 失败后 Redis 标记已存在）
- **触发→后果**：commit 失败/进程崩溃 → run 转 recoverable 暂停 → 用户 /retry 重烧整轮 codegen → 再次到 promote 时走 else 分支直接跳过 → qa_ok=True → DONE 并提示"版本 vX 可试玩"，而 current_version 从未抬升，用户玩到旧版本且无任何报错。
- **建议**：幂等标记放在 commit 成功之后置位（begin/commit 两段式），或 else 分支校验 DB 实际版本号等于候选版本再认为已 promote。

### P1-6 用户暂停检查点只含 design_doc，恢复后强制回 art_options 重烧

- **位置**：`backend/app/forge/graph.py:682-691`（`build_pause_checkpoint(phase="user_pause", design_doc=doc)` 未合并 existing）、`graph.py:772-774`（`user_pause` 无条件路由 `art_options`）；对照 `games/services.py:464-475` 的暂停会合并 existing keys——两个暂停写入方语义不一致
- **触发→后果**：在 code/qa 阶段点暂停 → art_options/候选版本/attempt/QA 进度全部丢失 → 续跑时重新调美术 LLM、重新弹 art_confirm、code 从 attempt=0 重烧，已确认的美术方向作废。
- **建议**：`build_pause_checkpoint` 统一走"读取现有 state 后覆盖少量字段"的合并语义，两个暂停入口共用。

### P1-7 resume grant 消费后崩溃 → run 永久卡 RUNNING，无任何回收者

- **位置**：`backend/app/forge/graph.py:1539-1559`（已核实：`st.pop("resume_grant")` + `run.status=RUNNING` 一并 commit，凭据不可恢复）；`scheduler/services.py:50-53`（`expire_stale_paused_runs` 只回收 PAUSED）
- **触发→后果**：恢复启动后任一 LLM 阶段崩溃 → broker 重投 resume 消息时 phase 仍在 HITL 集合且 grant 已被消费 → 当"陈旧消息"跳过 → run 永久停在 RUNNING；/retry 只接受 FAILED/PAUSED，用户唯一出路是取消重开，修改意见与已烧 token 全部作废。
- **建议**：① grant 消费延迟到首个非 HITL 节点成功后；② scheduler 增加 RUNNING 超时回收（如租约丢失 + N 分钟无心跳 → 置 FAILED 可 retry）。

### P1-8 邮件任务与长 run 共用单队列 + prefetch 池 → 验证码被阻塞数分钟

- **位置**：`backend/app/messaging/tasks.py`（五类 routing key 绑定同一 TASK_QUEUE）、`worker.py:256`（prefetch = max_concurrent_tasks = 3）
- **触发→后果**：3 个游戏生成占满 prefetch → 队列里验证码/重置密码邮件只能等任一 run 完成或 HITL 暂停 → 注册用户数分钟收不到验证码，高峰期反复发生。
- **建议**：邮件类任务拆独立队列（独立 consumer 或同一进程独立 channel/prefetch）。

### P1-9 任务失败重试无退避 + DLQ 无消费者 → 瞬时故障变永久丢失

- **位置**：`backend/app/messaging/worker.py:225-232`（普通失败路径零延迟立即 republish；已核实与 busy 路径不同）；DLQ 声明后全仓库无 consume/replay 调用；`email/worker.py` 的 aiosmtplib 未显式传 timeout（默认 60s）
- **触发→后果**：Postgres/SMTP 抖动 30 秒 → 每个 in-flight 任务数秒内连续失败 5 次 → 全部进 DLQ → 恢复后无人重放，需人工清理；期间 run 卡 RUNNING、用户收不到验证码。
- **建议**：重试带指数退避（延迟队列或 sleep）；提供 DLQ 重放工具脚本；SMTP 显式 timeout。

### P1-10 审核调用吃满 300s LLM 读超时，audit_request_timeout 只管流末等窗

- **位置**：`backend/app/forge/guard.py:264`（`provider.complete(..., max_tokens=2)` 用 `_llm_timeout()`=300s×3 次重试）、`guard.py:443`（输入审核 `await guard.audit(user_msg)` 无 wait_for）、`guard.py:510`（后台审核 task 无超时）
- **触发→后果**：审核端点建连成功但不回包 → 每次流式节点开头的输入审核最长阻塞 ~20 分钟，token 流一个字不出，远超 `audit_request_timeout=20s` 的设计意图；节点 TimeoutPolicy 兜底强杀后 RetryPolicy 又把"审核+生成"整轮重来。
- **建议**：所有 `guard.audit` 调用统一包 `asyncio.wait_for(settings.audit_request_timeout)`，与配置语义对齐。

### P1-11 code_or_repair 节点预算 420s，但内部串行工作量可达 ~2100s，系统性错配

- **位置**：`backend/app/forge/reliability/policy.py:30`（预算 = llm_request_timeout 300 + 120 = 420s）；内部：生成 LLM ≤300 + prepare 300 + 3 次构建×300 + 修复 LLM×300（`integration.py:94`、`config.py:69-72`）
- **触发→后果**：`build_pipeline_enabled=True` 时节点在第一次/第二次构建中途被 TimeoutPolicy 取消 → RetryPolicy 重试整节点再烧 420s → code_qa 外墙耗尽 → run 以超时收场，`build_max_retries` 形同虚设，npm install/构建全部白费。
- **建议**：code_or_repair 预算按 build 链开启状态动态计算（类似 code_qa_loop 外墙的 `attempts × per` 算法）。

### P1-12 Docker 基础设施故障被标为 failure_kind="build" → 进入 LLM 修复循环烧 token；sandbox_failed 恢复路径不可达

- **位置**：`backend/app/sandbox/docker.py:68-70`（`except DockerError: return BuildResult(ok=False, error="docker error: ...")` 不抛异常）、`backend/app/forge/code_qa_exec.py:461`（归为 build 失败）
- **触发→后果**：Docker daemon 宕机/镜像拉取失败 → diagnose → repair LLM → 再失败 → 烧完 `code_qa_max_attempts × build_max_retries` 轮 LLM 调用才以 qa_failed 暂停；reliability 层的 SandboxTimeout/SandboxOOM 字符串分类从不命中（BuildResult 只带 error 文本），`sandbox_failed` HITL 阶段全仓库无写入点，是死代码。
- **建议**：BuildResult 增加 `failure_kind` 字段（infra/build/timeout/oom），后端在对应分支主动填；reliability 分类只消费类型不嗅探中文文本（与 P2-8 同根）。

### P1-13 容器无 AutoRemove/reaper → worker 硬崩溃后容器与临时目录永久残留

- **位置**：`backend/app/sandbox/docker.py:129-131`（已核实 grep 全仓库无 AutoRemove/reaper）、清理仅靠进程内 finally；`docker.py:41` / `local.py:28` 的 `tempfile.mkdtemp` 目录同理
- **触发→后果**：worker 在执行中途被 OOM kill / 发版 kill -9 → 容器停留 `docker ps -a`、`gf-*-sandbox-*` 临时目录残留 → 磁盘缓慢打满、daemon 膨胀；无任何启动时/定时清扫。
- **建议**：容器加 `"AutoRemove": True`（配合容错删除）；worker 启动时清扫带命名前缀的孤儿容器与临时目录。

### P1-14 容器无日志轮转 + 全量 log() 读回内存 → 磁盘/内存双打爆

- **位置**：`backend/app/sandbox/docker.py:111`（HostConfig 无 LogConfig/max-size）、`docker.py:138` / `builder.py:229`（`container.log()` 一次性全量拉回）
- **触发→后果**：沙箱内死循环打印直到 timeout → json-file 日志无上限写 `/var/lib/docker` → 宿主磁盘打满、daemon 拒绝新建容器、全平台 run 失败；同时数百 MB 日志读进 worker 内存可能 OOM。builder.py:201-210 的 HostConfig 同缺。
- **建议**：HostConfig 加 `"LogConfig": {"Type": "json-file", "Config": {"max-size": "10m", "max-file": "3"}}`；`log(tail=N)` 限制读取量。

### P1-15 WS relay 任务在 try/finally 之外创建 → replay 期断连永久泄漏 channel/队列

- **位置**：`backend/app/ws/runs.py:121-124`（已核实：`relay = create_task(...)` 后 `await _replay_buffered(...)` 若抛错，relay 成为孤儿，try/finally 不覆盖这几行）
- **触发→后果**：客户端在 replay 最多 200 条缓冲事件期间断开（刷新页面，活跃 run 常见）→ relay 阻塞在 `replayed.wait()` 永不 set → 每次泄漏一个 channel + exclusive 队列直到进程重启；memory 模式下死队列持续无界堆积事件膨胀内存。
- **建议**：relay 创建后立即纳入 try/finally；`_await_disconnect` 也覆盖 replay 阶段。

### P1-16 超时只 kill 直接子进程，未建进程组 → 孙进程成孤儿继续跑并锁住 workspace

- **位置**：`backend/app/sandbox/local.py:117-122`（已核实：`proc.kill()` 无 killpg，`create_subprocess` 未用 `start_new_session`）、`backend/app/sandbox/builder.py:288-291` 同款
- **触发→后果**：build_cmd 超时 → 只杀 sh 外壳，pnpm/node/esbuild 孙进程继续占 CPU/内存、持有临时目录文件句柄 → pipeline 的 `TemporaryDirectory.__exit__` 在 Windows 上 rmtree 遇锁抛 OSError，把已判定超时的 run 再炸成意外失败；孤儿进程随超时次数累积。
- **建议**：`create_subprocess(..., start_new_session=True)`（POSIX）/ Windows 用 job object；kill 时杀整个进程组。

---

## P1 — 高优先级（安全）

### P1-17 /auth/verify-email 无限流，6 位纯数字验证码可爆破

- **位置**：`backend/app/api/auth.py:94`（已核实：全文件仅 register/login/resend/reset 四处有 check_rate_limit，verify-email 漏掉）；`auth/services.py:45`（`randbelow(1_000_000):06d`，TTL 600s，失败不计数不消费）
- **触发→后果**：攻击者用受害者邮箱注册 → 对 verify-email 不限速枚举 10^6 空间（数百 req/s 十分钟内命中）→ 以受害者邮箱完成验证 → 配合 OAuth 关联/密码重置路径接管账号。
- **建议**：verify-email 加 IP+邮箱双键限流；验证码校验失败 N 次作废重发。

### P1-18 OAuth callback 按 email 直接绑定已存在账号，未校验 email_verified → 账号预注册劫持

- **位置**：`backend/app/auth/oauth.py:149`（已核实：查到 existing User 即 add(OAuthAccount) 并 issue_session）
- **触发→后果**：攻击者先用受害者邮箱注册（自设密码）→ 受害者 OAuth 登录 → 身份被永久绑进攻击者掌握密码的账号；且该路径从不把 existing.email_verified 置 True，受害者被困在"未验证"账号里无法自助解绑。
- **建议**：email 绑定仅当 existing.email_verified 为真；否则走"邮箱验证后合并"流程。

### P1-19 openai_compat base_url 无主机限制 → 认证后 SSRF

- **位置**：`backend/app/llm/services.py:154`（test_draft_config/create_config 直接请求用户指定 URL）
- **触发→后果**：任意登录用户传 `base_url=http://169.254.169.254` 或内网地址 → 服务端发起内网请求，靠 error 文案/耗时差探测内网端口与服务；create_config 成功后每次 run 持续向该地址发请求。
- **建议**：base_url 做协议+主机白名单/黑名单（禁环回、链路本地、内网段），至少 test 端点要禁。

### P1-20 dev 调试路由完全无鉴权，仅靠 env 门控，而 env 默认值是 development

- **位置**：`backend/app/main.py:100`（`if settings.env == "development"` 才挂载）、`config.py:199`（`env: str = "development"`）
- **触发→后果**：生产漏配 ENV → `/api/v1/dev/verification-code?email=` 任意人可读他人邮箱验证码（配合 P1-17 直接接管）；`/dev/redis/flush` 全站登出/配额清零；`/dev/reset` 批量 fail 运行中 run。
- **建议**：dev 路由挂载增加显式开关（默认关）而非依赖 env 字符串；env=development 且非本机监听时启动警告。

### P1-21 prepare 阶段联网运行 + 共享 pnpm store 以 rw 挂载 → 跨租户供应链投毒

- **位置**：`backend/app/forge/build/dependency_preparer.py:71-77`（online 时 `network_mode=bridge`、store rw）、`builder.py:183-186`
- **触发→后果**：配合 P0-2 的 manifest 覆盖：攻击者的 run 在 prepare 阶段向共享 `/pnpm/store` 写入被篡改的包内容 → 后续所有用户的 offline build（信任 store）取到毒包 → 跨用户构建产物投毒；prepare 的外网访问也可作内网扫描跳板。
- **建议**：store 按租户隔离或 prepare 也走代理白名单；对 store 写入做内容校验（integrity manifest）。

### P1-22 token 配额只在 run 创建时 check-then-act 检查一次，run 中途无限超额

- **位置**：`backend/app/games/services.py:344`（仅 start_run 检查）；`forge/llm/client.py` 的 call_llm 全流程只有限流 + record_usage，无余量校验
- **触发→后果**：剩余配额 1000 时并发创建多个 run 全部通过检查后各自烧任意多；run 启动时剩 1 token，run 内 20+ 次 LLM 调用不再查配额——日/月限额形同虚设；而配额告警邮件声称"生成将挂起直至次日重置"，实际无任何挂起逻辑。
- **建议**：call_llm 记账前检查余量，超限抛 QPAUSED 类错误让 run 转可恢复暂停；或至少按 run 预算预扣。

### P1-23 试用账号"只读"仅前端承诺，后端只挡了密码/资料/点赞三处

- **位置**：`backend/app/auth/trial.py:26`（`reject_trial_mutation` 仅被 auth/profile/reactions 调用；games/runs/publish/llm_config 均无 trial 检查）
- **触发→后果**：`demo@gameforge.dev/password123` 公开在前端源码，任何人直接调 API 创建游戏、配 LLM key、启动 run、提交发布申请——所有试用用户共享同一日配额（一人耗尽全员不可用），且可向管理员审核队列灌垃圾。
- **建议**：trial 用户在烧钱/建状态端点统一拦截（依赖注入式 guard），或给 trial 独立极小配额。

---

## P1 — 高优先级（前端）

### P1-24 切换游戏不重置任何运行态 → 游戏 B 的页面持续显示并操作游戏 A 的 run

- **位置**：`frontend/src/pages/forge/ForgePage.tsx:235-238, 307`
- **问题**：路由 `/forge/A → /forge/B` 时组件不卸载，仅 `setGameId + resumedRef=null`；previewUrl/runId/runStatus/items/messages 全部残留。`if (preview && !previewUrl && token)` 因 previewUrl 还是 A 的旧值恒 false，B 的草稿预览永不铸出。
- **触发→后果**：B 的工坊渲染 A 的游戏试玩、A 的时间线/HITL 卡；用户在 B 页面点取消实际取消 A 的 run；A 的 localOnly 聊天消息混入 B 的聊天流。
- **建议**：routeGameId 变化时重置全部 run 相关 state（或给 ForgePage 加 key={gameId} 强制重挂载）。

### P1-25 WS 重连复用闭包捕获的过期 token → 4401 后静默永久放弃重连 + 误报"生成失败"

- **位置**：`frontend/src/ws/client.ts:46, 73`
- **触发→后果**：长 run（常超 15 分钟，超过 access token TTL）期间一次断网/休眠唤醒 → 重连仍带旧 token → 4401 → `return` 放弃重连且无提示 → 时间线/流式停更，还触发"生成失败"toast 而 run 实际正常；另无应用层心跳，半开连接要等 TCP 超时。
- **建议**：重连时从 auth store 重读最新 token；4401 时先刷新一次再重试；加心跳 ping/pong。

### P1-26 fetchDraftHtml 自行调用 refresh，绕过 client.ts 的单飞刷新 → 并发刷新可把有效会话登出

- **位置**：`frontend/src/lib/hosting.ts:92`
- **触发→后果**：access token 过期后草稿 fetch 与 react-query 请求同时 401 → 两路并发 refresh 同一旧 token → 轮换语义下后到者失败 → `if (store.refresh_token === refresh) clearSession()` 把仍有有效凭据的用户登出；client.ts:75-79 注释明示此风险但此处未复用单飞。
- **建议**：fetchDraftHtml 走 client.ts 导出的 single-flight refresh。

---

## P2 — 架构层次问题

### P2-1 HostingBackend 抽象不完整：write_version_layers/artifact_dir 直接穿透 local，S3 模式下产物只落本地盘，OSS 对象泄漏

- **位置**：`backend/app/hosting/store.py:24`（write_version_layers 永远 local，不经 get_hosting_backend）、`games/services.py:292`（prune 只 rmtree 本地，OSS 对象永久泄漏）、`s3.py:135` 注释宣称"真相源=OSS"而 `serve.py:62` 先读本地——SoT 互相矛盾
- **建议**：把 write_version_layers/删除/目录语义纳入 HostingBackend 协议，或明确 local 是 cache 层、所有语义操作走 backend。

### P2-2 HITL phase 词表是无枚举的影子状态机，4 个文件人肉同步

- **位置**：`graph.py:75`（`_HITL_RESUME_PHASES` 注释自认"与 app.api.runs._HITL_PHASES 对齐"）、`api/runs.py:146`、`dev/runtime.py:53`、`games/services.py:536`
- **建议**：phase 集合定义在 enums.py 紧邻 RunPhase/PauseReason，域层单点导出，API/dev 只消费不复制。漏改任意一处会产生"陈旧 resume 被放行/合法 resolve 被 409"类最难查的 bug。

### P2-3 错误分类靠中文错误文本嗅探，BuildResult 不携带 failure_kind

- **位置**：`backend/app/forge/reliability/errors.py:105-109`（`if "构建超时" in str(exc)`、`re.search(r"\boom\b")`）；生产者 `local.py:122`、`docker.py:137`、`builder.py:228` 各自硬编码同一句中文；对照 PlaytestResult 有 failure_kind 字段——同一仓库两套结果类型一套说分类语言一套不说
- **建议**：与 P1-12 合并修复：BuildResult 加 failure_kind，分类只消费类型。换 E2B 后端或改文案即静默退化为 WorkerInterrupted，影响 /retry 与告警路由。

### P2-4 checkpoint 双写 Redis+DB 但 revision 字段无人消费，Redis 残留旧值时从过期检查点恢复

- **位置**：`backend/app/forge/state.py:39, 51`（save_state 先 flush 后 r.set，提交由调用方稍后执行且无回滚钩子；load_state 优先 Redis；row.revision += 1 但全文件无 load 路径读它）
- **触发→后果**：① DB 提交成功而 Redis 写失败/failover 到旧副本 → 之后所有 load 优先返回旧状态，"确认了 B 方案却按 A 方案生成"；② 调用方事务回滚后 Redis 留下幻影 checkpoint/幻影 grant，重投的历史 resume 消息借幻影 grant 通过陈旧过滤擅自推进 run。
- **建议**：load 时比对 DB.revision（SELECT 单列代价极低）不一致则弃缓存；或 save 改为 commit 后写缓存 + 提供 invalidate。

### P2-5 provider 通用路径上叠厂商嗅探补丁 + usage 估算兜底（违反"不估算"红线）

- **位置**：`backend/app/llm/provider.py:158`（`"qwen3" in model` 子串判断注入 enable_thinking）、`_direct_hosts` 硬编码 8 个国内域名、`provider.py:528`（流式缺 usage 帧时 `char_count // 4` 估算 output、input 记 0，注释自认"已知例外"）
- **建议**：引入 provider profile（请求体钩子/代理策略/usage 提取策略可配置），新厂商只加 profile 不动主干；usage 缺帧时宁可记 0 并打标告警，估算值会系统性污染配额与报表（CLAUDE.md 明文"不估算"）。

### P2-6 沙箱 tier/超时配置三处三种形态，heavy 档不可达

- **位置**：`docker.py:25`（模块级 _TIERS 硬编码）、`local.py:19`（_TIMEOUT_S=60 私有常量）、builder 走 settings.builder_timeout_s；`sandbox/base.py:89`（生产唯一路径 `get_sandbox()` 的 `create()` 从不传 tier → heavy 档 1g/2cpu/120s 形同虚设，重构建被 60s 反复误杀）
- **建议**：tier→资源/超时映射收敛进 config.py 单表，`get_sandbox` 支持 tier 透传。

### P2-7 resolve_hitl 域状态机整段写在 API 路由层

- **位置**：`backend/app/api/runs.py:322`（80 行业务编排：锁、phase 校验、decision 白名单、状态迁移、入队凭据全在 router）；与 services.cancel_run/retry_run 分裂两处；`games/services.py:492` 的通用 /resume 只校验 status==PAUSED 就发 approve，完全绕过 decision 白名单——art_confirm 暂停时静默替用户选了方案 B
- **建议**：resolve/resume 逻辑下沉域层与 cancel/retry 并列，phase→decisions 映射单点定义。

---

## P2 — API 设计问题

### P2-8 建状态端点缺幂等五件套（项目明文约定）

- **位置**：`api/publish.py:38`（publish/submit 仅靠部分唯一索引兜底 409，无 Idempotency-Key/创建锁/限流）、`api/games.py:121`（POST /games 与 POST /games/fork/{slug} 五件套全无，fork 连唯一索引都没有；草稿数上限存在 TOCTOU——并发双击可突破 max_drafts_per_user）
- **建议**：对照 create_run（Idempotency-Key + run:create 锁 + 部分唯一索引）补齐；fork 至少加幂等键。

### P2-9 先查后写的并发竞态直接 500（无 IntegrityError 兜底）

- **位置**：`reactions/services.py:60`（toggle_reaction 并发双击 → uq_game_reaction 冲突 → 500）、`profile/services.py:35`（handle 抢名 → 500 而非 409 HANDLE_TAKEN）、`forge/memory/preferences.py:37`（upsert 同构竞态）
- **建议**：统一捕获 IntegrityError 转 409/幂等返回（publish.submit 已有同型兜底可复用）。

### P2-10 输入校验缺口 → 裸 500

- **位置**：`schemas/game.py:10`（GameCreate/GamePatch.title 无 max_length，超 DB String(255) → 500；requirement 无上限，与 RunCreate ≤2000 口径不一致；LLMConfigCreate.model/apikey 同样无上限）、`feedback/services.py:35`（run_id 声明为 str，`uuid.UUID()` 抛 ValueError → 500，应声明 UUID 自动 400）、`schemas/admin.py:37`（AdminSettings 裸 int 无 ge=1，管理员填 0 使全站用户立即 QUOTA_EXCEEDED）
- **建议**：补 Pydantic 约束（max_length/ge），feedback.run_id 改 UUID 类型。

### P2-11 列表接口无分页 → 全量拉取

- **位置**：`games/services.py:414`（GET /games/{id}/runs 无 limit，多轮对话长期累积数百 run 全量序列化）、`publish/services.py:131`（/publish/queue 带 status 查历史时全量；admin/audit-logs、admin/users 均有分页，此端点漏配）
- **建议**：补 limit/offset 或游标分页。

### P2-12 resolve_hitl 的防重锁无 try/finally + check-then-commit 竞态

- **位置**：`api/runs.py:336`（锁 SET 成功后业务段任一步抛错 → 锁留满 60s TTL，用户重试一律 409 与真实状态矛盾）、`runs.py:352-391`（读到 PAUSED 后经历多个 await 才 commit，无行锁/乐观锁；窗口内 scheduler 超时回收或 cancel 置 FAILED 后，resolve 的 commit 无条件覆盖回 RUNNING → 已回收的 run 复活继续烧 LLM）
- **建议**：锁包 try/finally；commit 改条件 UPDATE（WHERE status=PAUSED）或加 version 乐观锁。

### P2-13 限流键取 request.client.host，反代后全体用户共享一个桶

- **位置**：`api/auth.py:54-68`（login/register/resend/reset 均按 client.host）；对照 `hosting/routes.py:125` 却信任 x-forwarded-for——同一项目两套取 IP 策略
- **触发→后果**：生产经 nginx 后所有请求同源 IP → 攻击者单 IP 打满 30/min 即令全站用户登录持续 429（定向 DoS）。
- **建议**：统一可信代理层配置（uvicorn --proxy-headers + forwarded-allow-ips），限流键加账号维度。

---

## P2 — 运维与资源

### P2-14 task_outbox 只标记从不清理 + cancel 全表扫描

- **位置**：`messaging/outbox.py:28-36`（无 delete/purge；cancel_run_tasks 对全部未发布行全表拉取后 Python 逐行匹配 run_id）
- **建议**：定时清理已发布行（保留 N 天）；cancel 查询加 run_id 索引列或 JSON 谓词下推。

### P2-15 多 worker 副本调度扫描无行锁，单行 AppError 中断整轮

- **位置**：`scheduler/services.py:96-115`（查询无 with_for_update(skip_locked)；循环内 take_down 遇 INVALID_STATE 直接冒泡 → 本轮回滚，排在后面的到期游戏全部延迟且每分钟重复报错；expire_stale_paused_runs 与用户 resolve_hitl 在 48h 边界同样竞争）
- **建议**：SELECT FOR UPDATE SKIP LOCKED + per-row try/except。

### P2-16 RabbitWsBus 每条 WS 事件新建/关闭一个 channel（含 declare_exchange）

- **位置**：`messaging/rabbit.py:303`（流式打字机 80ms 微批 → 单 run ~12 channel/s，并发 3 run ~40 channel/s 的创建销毁，broker CPU/延迟被事件转发吃掉）
- **建议**：进程内复用长生命周期 channel + exchange declare 缓存。

### P2-17 事件循环上的同步阻塞 IO（同类多点）

- **位置**：`forge/build/pipeline.py:73`（TemporaryDirectory.__exit__ 同步 rmtree node_modules 数万小文件，Windows 达数秒，同 worker 其他 run/scheduler/outbox 全停摆）、`sandbox/builder.py:179`（`_ensure_bind_mount_permissions` 同步 rglob+chmod，超 90s 租约心跳无法续 → 租约被抢重复执行）、`games/official.py:282`（fork 时 shutil.copytree/rmtree 最高 50MB 同步拷贝）、`games/services.py:289`（prune_old_versions 同步 rmtree）
- **建议**：统一挪 `asyncio.to_thread`（注意与租约心跳的交互：to_thread 不阻塞事件循环，心跳可续）。

### P2-18 lifespan/worker 停机不释放 DB engine 与 Redis 池

- **位置**：`main.py:52`（lifespan 只 flush langfuse）、`worker.py` _consume finally（只关 RabbitMQ；handlers._worker_redis 第二个池与 engine 均不关）
- **触发→后果**：--reload/测试多次创建 app 时 Postgres 连接阶梯上涨触发 max_connections。
- **建议**：lifespan 收尾 engine.dispose() + pool.aclose()。

### P2-19 /preview/{token} 的 path label 未归一化 → Prometheus 序列无界膨胀

- **位置**：`core/metrics.py:65`（归一化只认 hex+连字符；token_urlsafe(32) 必含 g-z/_ → 原文进 label，每次预览新增 series；/play/{用户自定 slug} 随游戏数线性增长）
- **建议**：按路由模板（/preview/{token}、/play/{slug}）在注册处归一化。

### P2-20 analytics play_count 读-改-写丢更新 + UV 取可伪造 XFF

- **位置**：`analytics/store.py:57`（`play_count = play_count + 1` 非 SQL 原子自增，并发丢计数）、`hosting/routes.py:125`（visitor_id 取 X-Forwarded-For 可随意注水 30 日 UV，admin 报表失真）
- **建议**：`UPDATE ... SET play_count = play_count + 1`；UV 换签名 cookie 或至少去掉可伪造头。

---

## P2 — 其余 Sandbox/Forge 问题

### P2-21 DockerSandbox 容器以镜像默认用户运行 + 未复用 builder 的 uid 对齐 → build_cmd 写产物 EACCES

- **位置**：`docker.py:107-121`（无 User 键；镜像 USER sandbox uid 10001 对宿主 uid 建的 workspace 无写权限）；builder.py:195 的 `_docker_user_spec()` + `_ensure_bind_mount_permissions` 正是解同一问题的，sandbox 后端未复用。另：容器内若以 root 运行（某些镜像），配合 rw bind mount 存在逃逸放大面。
- **建议**：复用 builder 的 user spec 逻辑。

### P2-22 e2b stub 用模块级 _LIVE 全局持有活会话

- **位置**：`sandbox/e2b.py:21-48`（进程崩溃即泄漏远端沙箱持续计费；多 worker 进程各自为政）。当前默认关闭（ADR-03），PoC 阶段风险。
- **建议**：启用前改 DB 记录会话句柄 + 定时对账回收。

### P2-23 Backend 层写源文件 `workspace / rel` 无路径校验，纵深防御缺失

- **位置**：`local.py:80-86`、`docker.py:60-63`（完全依赖调用方 `_normalize_files` 过滤 `..`；当前唯一调用传固定键，不可达，但新增调用点即成逃逸面）。
- **建议**：backend 层统一校验 rel 规范化后仍在 workspace 内。

### P2-24 _qa_html（整份 index.html 含 base64）进图状态并扩散进主图 state

- **位置**：`forge/code_qa_exec.py:594`、`graph.py:1238`（`{**result}` 未剔除即并入主图；单 run 内存随产物体积无界增长，prefetch=N 放大 N 倍）。
- **建议**：子图终态白名单字段回传主图。

### P2-25 LangGraph RetryPolicy 不分异常类型：ContentAttacked/RunFinalized/AppError 都被整节点重试

- **位置**：`forge/reliability/policy.py:69`（RetryPolicy 未传 retry_on；guard 设计"命中即中止不重试"被破坏——攻击场景成本恰好翻倍；LLM_CONFIG_INVALID 类注定失败请求也多发一次；与 httpx ×4、code_qa attempt ×3、build 环 ×3、worker 重投 ×5 叠加，最坏一次 code 阶段放大到 70+ 次 LLM HTTP 调用；plan 节点内自修复 ×3 叠外层 ×2 = 最多 6 次 plan LLM 调用）
- **建议**：RetryPolicy 传 retry_on 排除业务性异常（ContentAttacked/AppError/RunFinalized）。

---

## P2 — 前端其余问题

### P2-26 8s 兜底轮询 effect 依赖每次渲染新建的 detail 对象 → interval 反复拆建可被流式渲染饿死

- **位置**：`ForgePage.tsx:430`（deps 含 useQuery 结果对象；流式期间每次 llm_delta 重渲染都 clearInterval+setInterval，轮询可能永远打不到后端——恰是 WS 半死时最需要兜底的时刻）
- **建议**：deps 收敛为原始值（runId/runStatus），或轮询挪入 react-query refetchInterval。

### P2-27 聊天 messages 无上限 + 每 delta 微批全量重渲染 1400 行页面

- **位置**：`ForgePage.tsx:468, 482-488`（timeline 有 slice(0,80) 上限，messages 无；ChatPanel 全量 map 无虚拟化无 memo）
- **建议**：messages 设上限 + 增量渲染（对最后一抽头 memo 或虚拟化）。

### P2-28 同一页面三套独立 run 状态轮询

- **位置**：`hooks/use-active-runs.ts:10`（ActiveRunBanner 8s 轮询 listActiveRuns）+ ForgePage 8s 轮询 getRun（纯 setState 不入 react-query 缓存）+ RunHistoryPanel ['game-runs']——三来源无共享去重，毫秒级不一致造成状态闪烁。
- **建议**：run 状态统一收敛 react-query 缓存键。

### P2-29 ChatPanel 无滚动跟随，流式输出与 HITL 卡片可能完全不可见

- **位置**：`ChatPanel.tsx:115`（panel 模式 overflow-y-auto 容器无任何 scrollTop/scrollIntoView 管理；HITL 决策卡渲染在滚动容器尾部，用户误以为生成卡死）。
- **建议**：追加消息时若接近底部则自动跟随；HITL 卡固定渲染。

### P2-30 refresh_token（30 天）明文存 localStorage + WS token 走 URL query

- **位置**：`stores/auth-store.ts:66`（一次 XSS 即长期静默控制账号；refresh 无会话族复用检测）、`ws/runs.py:101`（?token= 落代理/访问日志）。
- **建议**：refresh 改 httpOnly cookie + rotation 复用检测；WS 改首帧鉴权或短期票据。

---

## P2 — CLAUDE.md 约定违反（汇总）

| 约定 | 违反点 | 位置 |
|---|---|---|
| 禁硬编码密钥 | jwt_secret 默认值（P0-1）；trial 账号 password123 前后端各一份 | `config.py:17`、`auth/trial.py:18`、`frontend/src/lib/trial.ts` |
| usage 不估算 | 流式缺 usage 帧按字符数÷4 估算并写 Redis 计量 | `llm/provider.py:528`（见 P2-5） |
| 不硬编码游戏玩法 | 三款完整可玩小游戏源码（1227 行）硬编码并由业务模块 seed 成已发布游戏 | `scripts/official_assets/*.html` ← `games/official.py:215`（注：`forge/build/demos.py` 是构建管线验证 fixture，可豁免） |
| 禁止静默吞异常 | `list_models` 的 `except Exception: pass` 无任何日志；`official.py` `_copy_artifact` 源缺失静默 return（fork 出空产物 404 且无日志） | `llm/provider.py:218`、`games/official.py` |
| 幂等五件套 | publish/submit、POST /games、fork | 见 P2-8 |
| async 优先 | 官方游戏 fork 的同步 copytree | 见 P2-17 |
| 单文件 ≤500 行 / 单函数 ≤50 行 | `graph.py` 1505、`code_qa_exec.py` 623、`provider.py` 611、`games/services.py` 611、`prompts.py` 601、`guard.py` 571、`design_doc.py` 463；超 50 行函数：`run_generation` 173、`_repair_project` 203、`execute_code_or_repair` 176、`create_run` 109；前端 `ForgePage.tsx` 1366、`messages.ts` 1384（`types.gen.ts` 7403 为生成物豁免） | — |

---

## 修复优先级建议

**第一批（上线前必须）**：P0-1 ~ P0-4，P1-17/18/19/20（安全五连）、P1-2（消息丢失）。
**第二批（一周内）**：P1-1/3/4/5/6/7（worker 与状态机可靠性核心链）、P1-13/14/15/16（sandbox 与 WS 泄漏）、P1-24/25/26（前端三高）。
**第三批（排期偿还）**：其余 P1（配额、SSRF、邮件队列拆分）、P2 全部。
**专项重构建议**（跨多条问题共享根因）：
1. **超时体系**：基建客户端（DB/Redis/Docker）统一 timeout 层 → 消 P0-4、缓解 P1-1/10/11。
2. **failure_kind 贯通**：BuildResult/PlaytestResult 统一错误分类 → 消 P1-12、P2-3。
3. **checkpoint 单一真相源**：revision 校验或 commit-after-cache → 消 P2-4、P1-5/6/7 的共因。
4. **HITL 域层收口**：phase/decision 词表 + resolve/resume 下沉 services → 消 P2-2/7、P2-12。
5. **HostingBackend 协议补全** → 消 P2-1、P1-13 的产物残留部分。

---

*审查方法备注：候选发现约 79 条，去重合并为 56 条（多视角交叉确认：jwt_secret×2、consumer_timeout×2、RetryPolicy×2、list_models×2、进程组×2、verify-email×2 等）；关键机制性声明（compose restart 缺失、worker ack 模式、promote 时序、user_pause 检查点、grant 消费、manifest 覆盖、relay 作用域、verify-email 限流缺失、AutoRemove/LogConfig 缺失、db/redis 无超时参数）均已在源码逐行核实。*
