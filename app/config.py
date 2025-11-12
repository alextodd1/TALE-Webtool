from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration"""

    database_url: str
    secret_key: str
    debug: bool = False
    session_retention_days: int = 7
    host: str = "0.0.0.0"
    port: int = 8000

    # TALE Search defaults
    max_sequence_length: int = 100000
    min_tale_length: int = 10
    max_tale_length: int = 30
    min_spacer_length: int = 1
    max_spacer_length: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
