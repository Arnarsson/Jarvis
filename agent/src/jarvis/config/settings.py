"""Jarvis configuration settings using pydantic-settings."""

from functools import cached_property
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the Jarvis desktop agent.

    Settings are loaded from environment variables with the JARVIS_ prefix.
    For example, JARVIS_CAPTURE_INTERVAL=30 sets capture_interval to 30.
    """

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Capture settings
    capture_interval: int = 15  # seconds between captures
    idle_threshold: int = 300  # 5 minutes in seconds before pausing
    jpeg_quality: int = 80  # JPEG compression quality (1-100)

    # Server settings
    server_url: str = "http://localhost:8000"

    # File paths
    exclusions_file: Path = Path("~/.config/jarvis/exclusions.yaml")
    data_dir: Path = Path("~/.local/share/jarvis")

    # Logging
    log_level: str = "INFO"

    @field_validator("capture_interval")
    @classmethod
    def validate_capture_interval(cls, v: int) -> int:
        """Ensure capture interval is positive."""
        if v < 1:
            raise ValueError("capture_interval must be at least 1 second")
        return v

    @field_validator("jpeg_quality")
    @classmethod
    def validate_jpeg_quality(cls, v: int) -> int:
        """Ensure JPEG quality is within valid range."""
        if v < 1 or v > 100:
            raise ValueError("jpeg_quality must be between 1 and 100")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    @cached_property
    def exclusions_path(self) -> Path:
        """Return expanded exclusions file path."""
        return self.exclusions_file.expanduser()

    @cached_property
    def data_path(self) -> Path:
        """Return expanded data directory path."""
        return self.data_dir.expanduser()

    def load_exclusions(self) -> dict[str, list[str]]:
        """Load exclusion rules from YAML file.

        Returns a dictionary with:
        - app_names: List of application names to exclude
        - window_titles: List of window title patterns to exclude

        If the file doesn't exist, returns default exclusions.
        """
        default_exclusions = self._get_default_exclusions()

        if not self.exclusions_path.exists():
            return default_exclusions

        try:
            with open(self.exclusions_path) as f:
                user_exclusions = yaml.safe_load(f) or {}

            # Merge user exclusions with defaults
            return {
                "app_names": list(
                    set(default_exclusions.get("app_names", []))
                    | set(user_exclusions.get("app_names", []))
                ),
                "window_titles": list(
                    set(default_exclusions.get("window_titles", []))
                    | set(user_exclusions.get("window_titles", []))
                ),
            }
        except (yaml.YAMLError, OSError) as e:
            # Log error and return defaults
            import logging

            logging.warning(f"Failed to load exclusions from {self.exclusions_path}: {e}")
            return default_exclusions

    def _get_default_exclusions(self) -> dict[str, list[str]]:
        """Return default exclusion rules.

        These are bundled with the application and always applied.
        """
        return {
            "app_names": [
                "1password",
                "bitwarden",
                "lastpass",
                "keepass",
                "keepassxc",
                "keychain access",
                "gnome-keyring",
                "seahorse",
            ],
            "window_titles": [
                "private browsing",
                "incognito",
                "inprivate",
            ],
        }

    def is_excluded(self, app_name: str | None, window_title: str | None) -> bool:
        """Check if a window should be excluded from capture.

        Args:
            app_name: The application name (case-insensitive match)
            window_title: The window title (case-insensitive substring match)

        Returns:
            True if the window should be excluded, False otherwise.
        """
        exclusions = self.load_exclusions()

        # Check app name
        if app_name:
            app_lower = app_name.lower()
            for excluded_app in exclusions.get("app_names", []):
                if excluded_app.lower() in app_lower:
                    return True

        # Check window title
        if window_title:
            title_lower = window_title.lower()
            for excluded_title in exclusions.get("window_titles", []):
                if excluded_title.lower() in title_lower:
                    return True

        return False
