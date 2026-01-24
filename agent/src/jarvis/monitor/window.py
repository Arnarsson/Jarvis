"""Window monitoring and exclusion filtering using PyWinCtl."""

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import yaml


class WindowInfo(NamedTuple):
    """Information about a window.

    Attributes:
        app_name: The name of the application.
        window_title: The title of the window.
        is_active: Whether this is the currently active window.
    """

    app_name: str
    window_title: str
    is_active: bool


class WindowMonitor:
    """Monitors the active window using PyWinCtl.

    Provides information about the currently focused window including
    the application name and window title.

    Example:
        monitor = WindowMonitor()
        window = monitor.get_active_window()
        if window:
            print(f"Active: {window.app_name} - {window.window_title}")
    """

    def __init__(self) -> None:
        """Initialize the window monitor.

        No persistent state is needed as each call queries the current state.
        """
        pass

    def get_active_window(self) -> WindowInfo | None:
        """Get information about the currently active window.

        Returns:
            WindowInfo with app_name, window_title, and is_active=True,
            or None if no window is active (e.g., screen locked,
            no windows open, or error occurred).

        Note:
            On macOS, this may require Accessibility permissions.
            On Linux, works with X11 and Wayland (with limitations).
        """
        try:
            import pywinctl

            window = pywinctl.getActiveWindow()
            if window is None:
                return None

            # Get application name and window title safely
            app_name = window.getAppName() or ""
            window_title = window.title or ""

            return WindowInfo(
                app_name=app_name,
                window_title=window_title,
                is_active=True,
            )
        except Exception:
            # Handle any errors gracefully (permission denied, no display, etc.)
            return None


class ExclusionFilter:
    """Filters windows based on exclusion patterns.

    Matches window app names and titles against configured patterns
    to determine if capture should be skipped (for privacy).

    Example:
        exclusions = {
            "app_names": ["1password", "bitwarden"],
            "window_titles": ["private browsing"]
        }
        filter = ExclusionFilter(exclusions)

        window = WindowInfo("1Password 8", "Vault", True)
        should_exclude, pattern = filter.should_exclude(window)
        # should_exclude=True, pattern="1password"
    """

    def __init__(self, exclusions: dict) -> None:
        """Initialize the exclusion filter.

        Args:
            exclusions: Dictionary with keys:
                - "app_names": List of app name patterns to exclude
                - "window_titles": List of window title patterns to exclude
                Patterns are case-insensitive substring matches.
        """
        self.app_names: list[str] = [
            name.lower() for name in exclusions.get("app_names", [])
        ]
        self.window_titles: list[str] = [
            title.lower() for title in exclusions.get("window_titles", [])
        ]

    def should_exclude(self, window: WindowInfo | None) -> tuple[bool, str | None]:
        """Check if a window should be excluded from capture.

        Args:
            window: WindowInfo to check, or None if no active window.

        Returns:
            Tuple of (should_exclude, matched_pattern):
            - (True, pattern) if the window matches an exclusion pattern
            - (False, None) if the window should be captured
        """
        if window is None:
            # No window = capture is ok (probably on desktop or locked)
            return (False, None)

        # Check app name patterns
        app_lower = window.app_name.lower()
        for pattern in self.app_names:
            if pattern in app_lower:
                return (True, pattern)

        # Check window title patterns
        title_lower = window.window_title.lower()
        for pattern in self.window_titles:
            if pattern in title_lower:
                return (True, pattern)

        return (False, None)

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "ExclusionFilter":
        """Load exclusion patterns from a YAML file.

        Args:
            yaml_path: Path to YAML file with exclusion patterns.

        Returns:
            ExclusionFilter configured with patterns from file,
            or with empty lists if file not found or invalid.

        Example YAML format:
            app_names:
              - "1password"
              - "bitwarden"
            window_titles:
              - "private browsing"
        """
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            return cls(data)
        except (OSError, yaml.YAMLError):
            # File not found or invalid - return empty filter
            return cls({})
