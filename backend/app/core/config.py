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
    frontend_base_url: str = "http://127.0.0.1:5173"

    # 产物托管
    hosting_root: str = ".hosting"
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
    max_concurrent_runs: int = 3  # 每用户同时进行中的 run 上限（docs/05）
    max_versions_per_game: int = 20  # 版本保留上限（docs/04），超出删最旧
    max_drafts_per_user: int = 20  # 每用户草稿游戏数上限
    max_published_per_user: int = 50  # 每用户已发布游戏数上限
    system_daily_token_alert: int = 5_000_000  # 系统日用量告警阈值
    code_max_retries: int = 3  # code/qa 失败重试上限（docs/03）
    models_cache_ttl_s: int = 600  # /models 短期缓存（docs/05）

    # langfuse（SaaS Cloud，trace 上报）
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # 全局
    env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"


settings = Settings()
