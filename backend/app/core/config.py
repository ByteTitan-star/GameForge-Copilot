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

    # 加密与签名
    jwt_secret: str = "dev-secret-change-me-to-a-32-byte-random-string"
    jwt_access_ttl: int = 900  # access token 有效期（秒），15 分钟
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

    # 沙箱（local=子进程联调；docker=生产隔离，docs/09）
    sandbox_backend: str = "local"
    sandbox_image: str = "gameforge/sandbox"
    sandbox_default_tier: str = "standard"

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
    # LLM 连通测试（真实付费调用）每分钟上限，比通用限流更紧
    llm_probe_rate_limit_per_min: int = 5
    # create_run 幂等缓存有效期（秒）：同一 Idempotency-Key 在窗口内复用同一 run
    create_run_idempotency_ttl: int = 86_400
    max_concurrent_runs: int = 3  # 每用户同时进行中的 run 上限（docs/05）
    max_concurrent_tasks: int = 3  # worker 进程内同时处理的任务数（RabbitMQ prefetch_count）
    # LLM 熔断（按 user+provider）：连续失败达阈值后短时拒绝，避免雪崩打坏 key/配额
    llm_circuit_enabled: bool = True
    llm_circuit_failure_threshold: int = 5
    llm_circuit_open_s: int = 60
    max_versions_per_game: int = 20  # 版本保留上限（docs/04），超出删最旧
    max_drafts_per_user: int = 20  # 每用户草稿游戏数上限
    max_published_per_user: int = 50  # 每用户已发布游戏数上限
    system_daily_token_alert: int = 5_000_000  # 系统日用量告警阈值
    code_max_retries: int = 3  # code/qa 失败重试上限（docs/03）
    qa_max_retries: int = 2  # QA 试玩失败回退 code 重试上限
    art_max_retries: int = 2  # 美术 LLM 尝试次数，耗尽后走内置素材兜底
    # 封面截图开关：QA 通过后用 Playwright 截当前版本画面当封面。
    # 实际是否产出还依赖 PLAYTEST_USE_PLAYWRIGHT=1 且 worker 装了 chromium；否则降级无封面。
    thumbnail_enabled: bool = True
    models_cache_ttl_s: int = 600  # /models 短期缓存（docs/05）

    # langfuse（SaaS Cloud，trace 上报）
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://us.cloud.langfuse.com"

    # LLM HTTP 调用（complete() 的超时与 max_tokens）
    # 读超时：推理模型（qwen3-max/deepseek-r1 等）生整段代码可达数分钟，必须给足
    llm_request_timeout: int = 300
    # 建连/写/连接池超时（秒）；服务端不可达时应快速失败而非长等
    llm_connect_timeout: int = 30
    # 默认 max_tokens；推理模型的「思考 token」也计入此预算，故默认调高
    llm_max_tokens: int = 8192
    # 默认「直连（绕过桌面/系统代理）」的国内 LLM host，逗号分隔。
    # httpx 0.28 在 Windows 上会读注册表代理（即便无 *_PROXY 环境变量），
    # 国内 provider 走该代理常因代理无对应出口而超时；命中此处则强制直连。
    # 海外/未知 host 沿用默认（trust_env=True），保留「用代理访问 OpenAI 等」的能力。
    llm_direct_hosts: str = (
        "dashscope.aliyuncs.com,api.deepseek.com,api.moonshot.cn,"
        "open.bigmodel.cn,api.siliconflow.cn,api.minimaxi.com,"
        "api.baichuan-ai.com,api.lingyiwanwu.com"
    )
    # 是否对 qwen3 系列模型关掉 thinking（默认关）。
    # DashScope 约定「非流式调用必须 enable_thinking=false」，而 complete() 为非流式；
    # 关后既合规又省时省 token，避免思考链拉长触发读超时。需深度推理置 false（且需切到流式）。
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
    audit_interval_ms: int = 500  # 输出审核最小间隔（ms）：两次审核间最小时间窗
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
    log_level: str = "INFO"
    # 落盘目录：空=仓库根 logs/；-=仅 stdout（pytest）
    log_dir: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"


settings = Settings()
