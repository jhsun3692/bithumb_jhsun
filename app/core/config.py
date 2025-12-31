"""Application configuration settings."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Bithumb API
    bithumb_api_key: str = ""
    bithumb_api_secret: str = ""

    # Database
    database_url: str = "sqlite:///./db/trading.db"

    # Trading settings
    trading_enabled: bool = False
    default_currency: str = "KRW"
    default_coin: str = "BTC"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    enable_docs: bool = True  # Swagger/ReDoc 문서 활성화 (프로덕션에서는 False로 설정)

    # Security (JWT Authentication)
    jwt_secret_key: str = "change-this-to-a-random-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Scheduler settings
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 60  # Run strategy check every 60 seconds
    scheduler_timezone: str = "Asia/Seoul"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()