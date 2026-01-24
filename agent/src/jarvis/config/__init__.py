"""Jarvis configuration module.

Provides centralized configuration management using pydantic-settings.

Usage:
    from jarvis.config import get_settings

    settings = get_settings()
    print(settings.capture_interval)
    print(settings.load_exclusions())
"""

from functools import lru_cache

from jarvis.config.settings import Settings

__all__ = ["Settings", "get_settings"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns a singleton Settings instance that is cached for the lifetime
    of the application. This ensures consistent configuration across all
    modules.

    To reload settings, call get_settings.cache_clear() first.

    Returns:
        Settings instance loaded from environment variables.
    """
    return Settings()
