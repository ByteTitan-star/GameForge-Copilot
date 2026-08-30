from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，全部走环境变量（.env），禁硬编码密钥。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库与缓存（默认对接 docker-compose 本地容器）
    database_url: str = "postgresql+asyncpg://gameforge:gameforge@localhost:5432/gameforge"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://gameforge:gameforge@localhost:5672/"
    # rabbitmq | memory（pytest 默认 memory，见 conftest）
    messaging_backend: str = "rabbitmq"
    # ADR-09：基建客户端超时（秒）
    db_connect_timeout: int = 10
    db_command_timeout: int = 60
    redis_socket_connect_timeout: float = 5.0
    redis_socket_timeout: float = 5.0

    # 加密与签名
    jwt_secret: str = "dev-secret-change-me-to-a-32-byte-random-string"
    jwt_access_ttl: int = 7_200  # access token（秒），2h：覆盖长生成会话，前端仍可 refresh
    refresh_ttl: int = 2_592_000  # refresh token 有效期（秒），30 天
    verify_email_ttl: int = 600  # 邮箱验证码有效期（秒），默认 10 分钟
    password_reset_ttl: int = 3600  # 密码重置 token 有效期（秒），1 小时
    llm_apikey_encryption_key: str = ""

    # 邮件
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "GameForge"
    frontend_base_url: str = "http://127.0.0.1:5173"
    api_public_url: str = "http://127.0.0.1:8000"
    # 账号禁用时登录提示中的管理员联系邮箱（可被后台设置覆盖）
    admin_contact_email: str = ""

    # OAuth（B7）
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""

    # 产物托管
    hosting_root: str = ".hosting"
    hosting_backend: str = "local"  # local | s3
    artifact_max_size_mb: int = 50
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_bucket: str = ""
    s3_ak: str = ""
    s3_sk: str = ""
    s3_prefix: str = ""
    s3_addressing_style: str = "path"
    s3_connect_timeout: int = 10
    s3_read_timeout: int = 60

    # 沙箱：优先 Daytona（需 DAYTONA_API_KEY）；无 key 时工厂回退 docker→local
    sandbox_backend: str = "daytona"  # local|docker|daytona
    sandbox_image: str = "gameforge/sandbox"
    sandbox_default_tier: str = "standard"
    # P3.3：按源码体量 / engine / 近期 OOM·超时自动选 lite|standard|heavy
    sandbox_tier_auto: bool = True
    # Daytona：真实调用需 DAYTONA_API_KEY（禁止写入仓库）
    sandbox_daytona_enabled: bool = True
    daytona_api_key: str = ""
    daytona_timeout_s: int = 300  # 沙箱 create/exec 超时（秒）

    # 构建链（docs/build-pipeline.md P1+）
    build_pipeline_enabled: bool = False
    builder_backend: str = "docker"  # docker | local（local 需本机 pnpm，§24）
    builder_image: str = "gameforge-builder:v1"
    pnpm_store_path: str = ".pnpm-store"
    npm_registry: str = "https://registry.npmmirror.com"
    build_max_retries: int = 3
    source_artifact_max_size_mb: int = 20
    draft_url_ttl_s: int = 600
    builder_timeout_s: int = 300

    # 限流与配额
    default_daily_token_limit: int = 500_000
    default_monthly_token_limit: int = 10_000_000
    default_rate_limit_per_min: int = 30
    verify_email_max_failures: int = 5  # 验证码连续失败达限后作废 pending 码
    # LLM 连通测试（真实付费调用）每分钟上限，比通用限流更紧
    llm_probe_rate_limit_per_min: int = 5
    # create_run 幂等缓存有效期（秒）：同一 Idempotency-Key 在窗口内复用同一 run
    create_run_idempotency_ttl: int = 86_400
    max_concurrent_runs: int = 3  # 每用户同时进行中的 run 上限（docs/05）
    max_concurrent_tasks: int = 3  # worker 进程内同时处理的任务数（RabbitMQ prefetch_count）

    # 消费侧毒消息重试上限：超过后 ack 并写入 DLQ，避免无限 requeue 饿死 worker
    worker_max_redeliveries: int = 5

    # HIL / 用户暂停等待超时：PAUSED 超过此时长自动 FAILED，释放并发额度
    hil_wait_timeout_s: int = 172_800  # 默认 48h
    # RUNNING 且无执行租约、超过此时长无更新 → FAILED（ADR-10）
    # 正常生成有租约心跳，不会触发；仅兜底「崩溃后残留 RUNNING」
    running_stale_timeout_s: int = 7_200  # 2h，对齐长 CodeQaLoop
    # Docker container.log 有界读取行数（ADR-11）
    sandbox_log_tail: int = 2000

    # LLM 熔断（按 user+provider）：连续失败达阈值后短时拒绝，避免雪崩打坏 key/配额
    llm_circuit_enabled: bool = True
    llm_circuit_failure_threshold: int = 5
    llm_circuit_open_s: int = 60

    max_versions_per_game: int = 20  # 版本保留上限（docs/04），超出删最旧
    max_drafts_per_user: int = 20  # 每用户草稿游戏数上限
    max_published_per_user: int = 50  # 每用户已发布游戏数上限
    system_daily_token_alert: int = 5_000_000  # 系统日用量告警阈值
    # CodeQaLoop 总 attempt（含首次 generate）；infra/product/build 共用此预算。
    code_qa_max_attempts: int = 3
    # 单次 Forge Run 累计 LLM tokens 上限（input+output）；<=0 关闭。
    forge_run_max_tokens: int = 500_000
    # 跨阶段 REVISE_PLAN（qa/art 失败后改策划）独立预算，与 PLAN 同阶段 modify 无关。
    replan_max_revisions: int = 2
    # P0 可靠性：为 LangGraph 节点挂 TimeoutPolicy/RetryPolicy；关则保持旧行为便于回滚
    reliability_node_timeout: bool = True
    # P0 可靠性：副作用幂等（promote / usage 等）；关则跳过 Redis NX 门闩
    reliability_idempotent_side_effects: bool = True
    # P1 Memory：ContextBuilder 是否注入 recent turns；关则仍走 Builder，仅不带历史
    memory_context_builder: bool = True
    # P5：遗留 concat 已拆除；flag 仅兼容配置，不再切换拼装路径
    memory_context_enforcement: bool = True
    # P1 Memory：注入/写入 Explicit Preferences
    memory_preferences: bool = True
    # 从对话推断弱偏好；不得覆盖 Explicit；与 Explicit 合计最多 N 条 active
    memory_preferences_inferred: bool = True
    memory_preferences_max_active: int = 50
    # P1 Memory：ContextBuilder 总 token 预算（后续用 trace 标定）
    memory_context_budget_tokens: int = 4000

    # P1 Memory：超阈时刷新并持久化 Session Summary
    memory_session_summary: bool = True
    # Session Summary 优先 LLM（失败回落确定性）
    memory_session_summary_llm: bool = True

    # P2 Skills：节点经 catalog/router；先暴露 name/description，正文按需加载
    skills_router_enabled: bool = True
    # Methodology 由 LLM 在节点候选内自选（仅看 id/name/description）；Policy 永不 LLM
    skills_llm_selection: bool = True
    # 质量 lift A/B 允许走 LLM complete（评估脚本用）
    skills_quality_lift_llm: bool = True

    # P4 Exact Cache：仅白名单低熵节点
    exact_cache_enabled: bool = True
    exact_cache_ttl_s: int = 86_400
    # P4.5 / ADR-06：Semantic shadow + Pinecone 分层命中
    semantic_cache_shadow_enabled: bool = True
    semantic_cache_shadow_ttl_s: int = 604_800
    semantic_cache_direct_hit_enabled: bool = True
    # < soft miss；[soft, hard) LLM 确认；>= hard 直接返回
    semantic_cache_soft_threshold: float = 0.85
    semantic_cache_hard_threshold: float = 0.95

    # Embedding（OpenAI-compat /embeddings）；默认轻量中文 bge-small-zh-v1.5
    embedding_enabled: bool = True
    embedding_provider: str = "openai_compat"
    embedding_model: str = "bge-small-zh-v1.5"
    embedding_apikey: str = ""
    embedding_base_url: str = ""
    embedding_timeout_s: int = 30

    # Pinecone（无 api_key+host 则语义命中空操作；REST，不强制 pinecone SDK）
    pinecone_enabled: bool = True
    pinecone_api_key: str = ""
    pinecone_host: str = ""  # 例：xxxx.svc.aped-xxxx.pinecone.io
    pinecone_index: str = "gameforge-semantic"
    pinecone_namespace: str = "default"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # ADR-14 Knowledge RAG（独立 Index；禁止 fallback 到 PINECONE_HOST）
    knowledge_rag_enabled: bool = False
    pinecone_knowledge_host: str = ""
    pinecone_knowledge_namespace: str = "global"
    pinecone_knowledge_index: str = "gameforge-knowledge"
    knowledge_rag_inject_plan: bool = True
    knowledge_rag_inject_revise: bool = True
    knowledge_rag_inject_art: bool = False
    knowledge_rag_inject_code: bool = False
    knowledge_retrieve_k: int = 12
    knowledge_rerank_top_n: int = 4
    knowledge_semantic_rerank_enabled: bool = True
    # top1−top2 retrieval_score 差距 ≥ 此值时跳过同模型二次 embed（0=禁用跳过）
    knowledge_rerank_min_score_gap: float = 0.12
    knowledge_token_budget: int = 800
    knowledge_query_max_tokens: int = 480
    knowledge_min_relevance_score: float = 0.35
    knowledge_retrieve_timeout_s: float = 8.0
    knowledge_circuit_enabled: bool = True
    knowledge_circuit_failure_threshold: int = 5
    knowledge_circuit_open_s: float = 30.0
    knowledge_embedding_expected_dim: int = 0  # 0=跳过；生产 bge-small-zh-v1.5 设为 512
    knowledge_embedding_expected_model: str = ""  # 空=跳过；应与 EMBEDDING_MODEL 一致
    knowledge_embedding_version: str = ""  # 空=跳过；ingest 写入 metadata.embedding_version
    knowledge_metadata_validation_enabled: bool = True

    # ADR-13 Native Engine（Godot-first；默认关，不影响 Web 管线）
    native_engine_enabled: bool = False
    native_engine_godot_version: str = "4.3"
    native_engine_godot_bin: str = ""
    native_engine_godot_docker_image: str = ""
    native_engine_godot_build_timeout_s: int = 120
    native_engine_godot_run_timeout_s: int = 30

    # 偏好抽取：仅轻量 chat；未配置 model 则不自动写偏好（禁止规则正式路径）
    preference_extract_enabled: bool = True
    preference_extract_provider: str = "openai_compat"
    preference_extract_model: str = ""
    preference_extract_apikey: str = ""
    preference_extract_base_url: str = ""

    # 语义软命中确认 LLM（空则回退 preference_extract_*）
    semantic_confirm_provider: str = "openai_compat"
    semantic_confirm_model: str = ""
    semantic_confirm_apikey: str = ""
    semantic_confirm_base_url: str = ""

    art_max_retries: int = 2  # 美术 LLM 尝试次数，耗尽后走内置素材兜底
    # 美术 A/B 是否并行各调一次模型（更快、成本约 2 倍）；关则单次返回两套
    forge_art_options_parallel: bool = True
    # 试玩前按策划稿做静态验收（引擎/输入/HUD 等）；关则仅结构+浏览器冒烟
    forge_acceptance_gate: bool = True
    # 试玩会话内按 acceptance_criteria 做运行时状态探针
    forge_acceptance_runtime: bool = True
    # 封面截图：QA 通过后用 Playwright 截当前 candidate。Worker 必须具备 Chromium。
    thumbnail_enabled: bool = True
    models_cache_ttl_s: int = 600  # /models 短期缓存（docs/05）

    # langfuse（SaaS Cloud，trace 上报）
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://us.cloud.langfuse.com"

    # LLM HTTP 调用（complete() 的超时与 max_tokens）
    # 读超时：推理模型生整段代码可达数分钟；默认 600 覆盖慢模型
    llm_request_timeout: int = 600
    # 建连/写/连接池超时（秒）；服务端不可达时应快速失败而非长等
    llm_connect_timeout: int = 30
    # 传输层有限重试：瞬时网络抖动 / 429 / 502-504；与业务自修复预算正交
    llm_http_max_retries: int = 3
    llm_http_retry_base_delay_s: float = 0.5
    # 默认 max_tokens（plan/art/qa 等）；GLM 冗长设计稿 JSON 在 8k 易截断，默认 24k
    llm_max_tokens: int = 24576
    # Code 阶段单独上限（整段 HTML / project JSON 体量大）
    llm_code_max_tokens: int = 32768
    # 输出截断后最多续写轮数（每轮独立 LLM 调用）
    llm_continuation_max_rounds: int = 3
    # 续写 prompt 携带的已生成内容尾部字符数
    llm_continuation_tail_chars: int = 8000
    # 默认「直连（绕过桌面/系统代理）」的国内 LLM host，逗号分隔。
    # httpx 0.28 在 Windows 上会读注册表代理（即便无 *_PROXY 环境变量），
    # 国内 provider 走该代理常因代理无对应出口而超时；命中此处则强制直连。
    # 海外/未知 host 沿用默认（trust_env=True），保留「用代理访问 OpenAI 等」的能力。
    llm_direct_hosts: str = (
        "dashscope.aliyuncs.com,api.deepseek.com,api.moonshot.cn,"
        "open.bigmodel.cn,api.siliconflow.cn,api.minimaxi.com,"
        "api.baichuan-ai.com,api.lingyiwanwu.com"
    )
    # 默认关 thinking：见 app.llm.thinking 厂商能力表（Qwen/GLM/DeepSeek/Kimi/…）。
    # 避免思考链占满 max_tokens。需深度推理置 false。
    llm_disable_thinking: bool = True

    # 流式输出（打字机）：complete_stream 微批 LLM_DELTA 事件给前端。关闭则 run_streamed_llm
    # 退化为非流式 _llm（流式体验与输出审核都停）。docs/护栏机制设计。
    stream_enabled: bool = True
    stream_batch_chars: int = 4  # 微批字符数：攒够这么多字发一个 LLM_DELTA
    stream_batch_ms: int = 80  # 微批时间窗（ms）：超时强制 flush，避免末批滞留

    # 平台预设审核模型：护栏用，与用户 LLM 配置无关，明文 env（同 s3_sk/smtp_pass）。
    # audit_enabled=False 或 audit_model 空 → build_guard 返回 NoopGuard（审核完全不生效）。
    audit_enabled: bool = True
    audit_provider: str = "openai_compat"  # 审核走哪个 provider（默认兼容协议，运营自填 base_url）
    audit_model: str = ""  # 必填，如 gpt-4o-mini / qwen-plus；空则审核降级为仅正则快筛
    audit_apikey: str = ""  # 平台 key，单独 env，不进用户配置表
    audit_base_url: str = ""  # compat 必填
    audit_interval_ms: int = (
        60_000  # 输出审核最小间隔（ms）：两次审核间最小时间窗（默认 1 分钟；admin 后台可调）
    )
    audit_min_chars_between: int = 80  # 输出审核最小字符增量：攒够这么多字才触发一次
    audit_max_buffer_chars: int = 1500  # 审核滑窗上限：只取最近这么多字，避免越审越贵
    audit_request_timeout: int = 20  # 审核读超时（秒，短，避免拖垮打字机体验）
    audit_quick_filter: bool = True  # 正则前置快筛开关：命中即决，不调 LLM
    # 快筛黑名单文件路径：空=内置 app/forge/blacklist.txt（docker 可挂载外部文件覆盖）
    audit_blacklist_file: str = ""
    # AC 敏感词词库：关则只跑 blacklist.txt；目录空=内置 app/forge/lexicons/
    audit_lexicon_enabled: bool = True
    audit_lexicon_dir: str = ""

    # 全局
    env: str = "development"
    # ADR-07 P1-20：dev 调试路由显式开关（默认关；本地/pytest 在 .env 或 conftest 打开）
    dev_routes_enabled: bool = False
    log_level: str = "INFO"
    # 落盘目录：空=仓库根 logs/；-=仅 stdout（pytest）
    log_dir: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"


settings = Settings()
