"""Meeting detection via window title pattern matching."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class MeetingPlatform(str, Enum):
    """Detected meeting platform."""

    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    TEAMS = "teams"
    GENERIC = "generic"


@dataclass
class MeetingState:
    """Current meeting state."""

    in_meeting: bool
    platform: Optional[MeetingPlatform]
    started_at: Optional[datetime]
    window_title: Optional[str]


# Patterns to detect meeting applications
# Format: (regex pattern, platform)
MEETING_PATTERNS = [
    # Zoom - matches "Zoom Meeting", "Zoom Webinar", zoom.us in browser
    (r"zoom\s*(meeting|webinar)?", MeetingPlatform.ZOOM),
    (r"zoom\.us", MeetingPlatform.ZOOM),
    # Google Meet - matches meet.google.com in browser, "Google Meet" app
    (r"meet\.google\.com", MeetingPlatform.GOOGLE_MEET),
    (r"google\s+meet", MeetingPlatform.GOOGLE_MEET),
    # Microsoft Teams - matches "Microsoft Teams", "| Meeting |" in title
    (r"microsoft\s+teams", MeetingPlatform.TEAMS),
    (r"\|\s*meeting\s*\|.*teams", MeetingPlatform.TEAMS),
    # Generic patterns (less reliable, checked last)
    (r"(meeting|call)\s+with", MeetingPlatform.GENERIC),
]


class MeetingDetector:
    """Detects active meetings from window information.

    Monitors window titles and application names to detect when the user
    is in a video meeting (Zoom, Google Meet, Microsoft Teams).

    Example:
        detector = MeetingDetector()
        state = detector.check_window("Zoom", "Zoom Meeting")
        if state.in_meeting:
            print(f"In {state.platform.value} meeting since {state.started_at}")
    """

    def __init__(self) -> None:
        """Initialize the meeting detector."""
        self._current_state = MeetingState(
            in_meeting=False,
            platform=None,
            started_at=None,
            window_title=None,
        )
        self._patterns = [
            (re.compile(p, re.IGNORECASE), platform)
            for p, platform in MEETING_PATTERNS
        ]

    @property
    def current_state(self) -> MeetingState:
        """Get the current meeting state."""
        return self._current_state

    def check_window(self, app_name: str, window_title: str) -> MeetingState:
        """Check if current window indicates an active meeting.

        Args:
            app_name: Name of the active application
            window_title: Title of the active window

        Returns:
            Updated MeetingState
        """
        combined_text = f"{app_name} {window_title}".lower()

        # Check each pattern
        detected_platform = None
        for pattern, platform in self._patterns:
            if pattern.search(combined_text):
                detected_platform = platform
                break

        was_in_meeting = self._current_state.in_meeting
        now_in_meeting = detected_platform is not None

        # State transitions
        if now_in_meeting and not was_in_meeting:
            # Meeting started
            self._current_state = MeetingState(
                in_meeting=True,
                platform=detected_platform,
                started_at=datetime.now(timezone.utc),
                window_title=window_title,
            )
            logger.info(
                "meeting_detected platform=%s window_title=%s",
                detected_platform.value,
                window_title,
            )

        elif not now_in_meeting and was_in_meeting:
            # Meeting ended
            duration = 0.0
            if self._current_state.started_at:
                duration = (
                    datetime.now(timezone.utc) - self._current_state.started_at
                ).total_seconds()
            logger.info(
                "meeting_ended platform=%s duration_seconds=%.1f",
                self._current_state.platform.value
                if self._current_state.platform
                else None,
                duration,
            )
            self._current_state = MeetingState(
                in_meeting=False,
                platform=None,
                started_at=None,
                window_title=None,
            )

        elif now_in_meeting:
            # Still in meeting - update window title if changed
            if window_title != self._current_state.window_title:
                self._current_state = MeetingState(
                    in_meeting=True,
                    platform=self._current_state.platform,
                    started_at=self._current_state.started_at,
                    window_title=window_title,
                )

        return self._current_state

    def reset(self) -> None:
        """Reset meeting state (e.g., on agent restart)."""
        self._current_state = MeetingState(
            in_meeting=False,
            platform=None,
            started_at=None,
            window_title=None,
        )
