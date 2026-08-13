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
    s3_bucket: str = ""
    s3_ak: str = ""
    s3_sk: str = ""

    # 沙箱（local=子进程联调；docker=生产隔离，docs/09）
    sandbox_backend: str = "local"
    sandbox_image: str = "gameforge/sandbox"
    sandbox_default_tier: str = "standard"

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
    max_versions_per_game: int = 20  # 版本保留上限（docs/04），超出删最旧
    max_drafts_per_user: int = 20  # 每用户草稿游戏数上限
    max_published_per_user: int = 50  # 每用户已发布游戏数上限
    system_daily_token_alert: int = 5_000_000  # 系统日用量告警阈值
    code_max_retries: int = 3  # code/qa 失败重试上限（docs/03）
    qa_max_retries: int = 2  # QA 试玩失败回退 code 重试上限
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

    # 全局
    env: str = "development"
    log_level: str = "INFO"
    # 落盘目录：空=仓库根 logs/；-=仅 stdout（pytest）
    log_dir: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"


settings = Settings()
