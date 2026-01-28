"""Server configuration with environment variable loading."""

import functools
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Jarvis server settings.

    All settings can be overridden via environment variables with JARVIS_ prefix.
    Example: JARVIS_DATABASE_URL, JARVIS_LOG_LEVEL
    """

    # Database
    database_url: str = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"

    # Vector storage
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Redis (for ARQ task queue)
    redis_host: str = "localhost"
    redis_port: int = 6379

    # File storage
    storage_path: Path = Path("/data/captures")
    data_dir: Path = Path("/data")

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: list[str] = ["*"]

    # API Keys
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # Google Calendar
    google_credentials_path: Path | None = None

    # Focus Inbox
    # Comma-separated list of sender emails considered VIP.
    vip_senders: list[str] = []

    model_config = {
        "env_prefix": "JARVIS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Ignore unknown env vars (e.g., POSTGRES_* for docker)
    }


@functools.lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Settings are loaded once and cached for the lifetime of the process.
    Use this function for dependency injection in FastAPI.
    """
    return Settings()
