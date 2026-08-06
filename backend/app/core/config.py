from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，全部走环境变量（.env），禁硬编码密钥。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库与缓存
    database_url: str = ""
    redis_url: str = ""

    # 加密与签名
    jwt_secret: str = "dev-secret-change-me"
    llm_apikey_encryption_key: str = ""

    # 邮件
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""

    # 产物托管
    hosting_root: str = ""
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_ak: str = ""
    s3_sk: str = ""

    # 沙箱
    sandbox_image: str = "gameforge/sandbox"
    sandbox_default_tier: str = "standard"

    # 限流与配额
    default_daily_token_limit: int = 500_000
    default_rate_limit_per_min: int = 30

    # langfuse（SaaS Cloud，trace 上报）
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # 全局
    env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"


settings = Settings()
