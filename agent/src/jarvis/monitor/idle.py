"""Idle detection using pynput for monitoring user input activity."""

import threading
import time
from typing import Callable

from pynput import keyboard, mouse


class IdleDetector:
    """Detects user idle state by monitoring keyboard and mouse input.

    Uses pynput listeners to track the last input activity and determine
    if the user has been idle for longer than the configured threshold.

    Example:
        detector = IdleDetector(idle_threshold=300.0)  # 5 minutes
        detector.start()
        try:
            while True:
                if detector.is_idle():
                    print("User is idle")
                time.sleep(1)
        finally:
            detector.stop()

    Context manager usage:
        with IdleDetector(idle_threshold=300.0) as detector:
            while True:
                print(f"Idle: {detector.is_idle()}")
                time.sleep(1)
    """

    def __init__(self, idle_threshold: float = 300.0) -> None:
        """Initialize the idle detector.

        Args:
            idle_threshold: Seconds of inactivity before considered idle.
                           Default is 300.0 (5 minutes).
        """
        self.idle_threshold = idle_threshold
        self._last_activity: float = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None

    def _on_activity(self, *args: object) -> None:
        """Callback for any input activity.

        Updates the last activity timestamp in a thread-safe manner.
        Called by pynput listeners on mouse/keyboard events.
        """
        with self._lock:
            self._last_activity = time.monotonic()

    def is_idle(self) -> bool:
        """Check if the user is currently idle.

        Returns:
            True if time since last activity exceeds idle_threshold,
            False otherwise.
        """
        with self._lock:
            if self._last_activity == 0.0:
                return False
            return (time.monotonic() - self._last_activity) > self.idle_threshold

    def get_idle_time(self) -> float:
        """Get the time in seconds since the last activity.

        Returns:
            Seconds since last input activity. Returns 0.0 if no activity
            has been recorded yet.
        """
        with self._lock:
            if self._last_activity == 0.0:
                return 0.0
            return time.monotonic() - self._last_activity

    def start(self) -> None:
        """Start monitoring for input activity.

        Creates and starts mouse and keyboard listeners. Initializes
        the last activity timestamp to the current time.

        Note:
            On macOS, this requires Accessibility permissions.
            On Linux, requires X11 or appropriate permissions.
        """
        if self._running:
            return

        with self._lock:
            self._last_activity = time.monotonic()

        # Create mouse listener
        self._mouse_listener = mouse.Listener(
            on_move=self._on_activity,
            on_click=self._on_activity,
            on_scroll=self._on_activity,
        )

        # Create keyboard listener
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_activity,
        )

        # Start listeners
        self._mouse_listener.start()
        self._keyboard_listener.start()
        self._running = True

    def stop(self) -> None:
        """Stop monitoring for input activity.

        Stops and cleans up the mouse and keyboard listeners.
        """
        if not self._running:
            return

        self._running = False

        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None

        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def __enter__(self) -> "IdleDetector":
        """Enter context manager, starting the detector."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager, stopping the detector."""
        self.stop()
