"""Main capture loop integrating screenshot, change detection, and privacy filters."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from PIL import Image

from jarvis.capture import ChangeDetector, ScreenCapture
from jarvis.config import Settings
from jarvis.monitor import ExclusionFilter, IdleDetector, WindowMonitor

logger = logging.getLogger(__name__)


class CaptureState(Enum):
    """State of the capture loop."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class CaptureResult:
    """Result of a successful capture."""

    monitor_index: int
    image: Image.Image
    jpeg_bytes: bytes
    timestamp: datetime
    reason: str  # first_capture, interval_elapsed, content_changed


class CaptureLoop:
    """Main capture loop that coordinates all capture components.

    Integrates ScreenCapture, ChangeDetector, IdleDetector, WindowMonitor,
    and ExclusionFilter into a unified capture system.

    The loop runs on a 1-second tick but the ChangeDetector determines
    if an actual capture should happen based on content change or interval.

    Example:
        loop = CaptureLoop(settings)
        loop.on_capture(lambda r: print(f"Captured: {r.reason}"))
        await loop.start()
    """

    def __init__(self, config: Settings) -> None:
        """Initialize the capture loop.

        Args:
            config: Settings instance with capture configuration
        """
        self.config = config

        # Create component instances
        self._screen_capture = ScreenCapture(jpeg_quality=config.jpeg_quality)
        self._change_detector = ChangeDetector(min_interval=float(config.capture_interval))
        self._idle_detector = IdleDetector(idle_threshold=float(config.idle_threshold))
        self._window_monitor = WindowMonitor()
        self._exclusion_filter = ExclusionFilter(config.load_exclusions())

        # State
        self._state = CaptureState.STOPPED

        # Watchdog: Track last successful capture to detect hangs
        self._last_capture_timestamp: datetime | None = None
        self._watchdog_timeout = timedelta(minutes=5)
        self._consecutive_errors = 0
        self._max_consecutive_errors = 10

        # Callbacks
        self._capture_callbacks: list[Callable[[CaptureResult], None]] = []
        self._skip_callbacks: list[Callable[[str], None]] = []
        self._state_change_callbacks: list[Callable[[CaptureState], None]] = []

    @property
    def state(self) -> CaptureState:
        """Get current loop state."""
        return self._state

    @property
    def last_capture_time(self) -> datetime | None:
        """Get timestamp of last successful capture for health monitoring."""
        return self._last_capture_timestamp

    def on_capture(self, callback: Callable[[CaptureResult], None]) -> None:
        """Register callback for when a capture occurs.

        Args:
            callback: Function called with CaptureResult when capture happens
        """
        self._capture_callbacks.append(callback)

    def on_skip(self, callback: Callable[[str], None]) -> None:
        """Register callback for when a capture is skipped.

        Args:
            callback: Function called with reason string when capture skipped
        """
        self._skip_callbacks.append(callback)

    def on_state_change(self, callback: Callable[[CaptureState], None]) -> None:
        """Register callback for state changes.

        Args:
            callback: Function called with new CaptureState on state change
        """
        self._state_change_callbacks.append(callback)

    def _set_state(self, new_state: CaptureState) -> None:
        """Set state and notify callbacks."""
        if self._state != new_state:
            self._state = new_state
            for callback in self._state_change_callbacks:
                try:
                    callback(new_state)
                except Exception:
                    pass  # Don't let callback errors break the loop

    def _notify_capture(self, result: CaptureResult) -> None:
        """Notify capture callbacks."""
        for callback in self._capture_callbacks:
            try:
                callback(result)
            except Exception:
                pass

    def _notify_skip(self, reason: str) -> None:
        """Notify skip callbacks."""
        for callback in self._skip_callbacks:
            try:
                callback(reason)
            except Exception:
                pass

    async def start(self) -> None:
        """Start the capture loop.

        Starts the idle detector and enters the main loop.
        Runs until stop() is called.
        """
        self._idle_detector.start()
        self._set_state(CaptureState.RUNNING)
        await self._run_loop()

    async def _run_loop(self) -> None:
        """Main capture loop.

        Runs on a 1-second tick but actual captures are determined
        by the change detector's hybrid trigger logic.
        """
        while self._state == CaptureState.RUNNING:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log and continue on errors
                pass

            # Wait 1 second before next tick
            await asyncio.sleep(1.0)

    async def _tick(self) -> None:
        """Single tick of the capture loop with watchdog and error recovery."""
        # Watchdog check: detect if capture loop is hung
        if self._last_capture_timestamp:
            time_since_capture = datetime.utcnow() - self._last_capture_timestamp
            if time_since_capture > self._watchdog_timeout:
                logger.warning(
                    "Watchdog triggered: No capture in %d seconds. Attempting recovery...",
                    time_since_capture.total_seconds()
                )
                await self._attempt_recovery()
        
        # Check if paused
        if self._state == CaptureState.PAUSED:
            return

        # Check idle state
        if self._idle_detector.is_idle():
            self._notify_skip("user_idle")
            return

        # Check exclusion filter
        window = self._window_monitor.get_active_window()
        should_exclude, pattern = self._exclusion_filter.should_exclude(window)
        if should_exclude:
            self._notify_skip(f"excluded_app: {pattern}")
            return

        # Capture active monitors with better error handling
        try:
            captures = self._screen_capture.capture_active()
            # Reset error counter on success
            self._consecutive_errors = 0
        except Exception as e:
            self._consecutive_errors += 1
            error_msg = str(e)
            logger.error(
                "Capture failed (attempt %d/%d): %s",
                self._consecutive_errors,
                self._max_consecutive_errors,
                error_msg,
                exc_info=True if self._consecutive_errors < 3 else False
            )
            self._notify_skip(f"capture_error: {error_msg}")
            
            # If too many consecutive errors, attempt recovery
            if self._consecutive_errors >= self._max_consecutive_errors:
                logger.critical(
                    "Too many consecutive capture errors (%d). Attempting recovery...",
                    self._consecutive_errors
                )
                await self._attempt_recovery()
            return

        # Process each capture
        for monitor_index, image, jpeg_bytes in captures:
            should_capture, reason = self._change_detector.should_capture(
                monitor_index, image
            )

            if should_capture:
                # Record the capture
                self._change_detector.record_capture(monitor_index, image)

                # Update last capture timestamp for watchdog
                self._last_capture_timestamp = datetime.utcnow()

                # Create result and notify
                result = CaptureResult(
                    monitor_index=monitor_index,
                    image=image,
                    jpeg_bytes=jpeg_bytes,
                    timestamp=self._last_capture_timestamp,
                    reason=reason,
                )
                self._notify_capture(result)
                logger.debug("Capture successful: monitor=%d, reason=%s", monitor_index, reason)
            else:
                self._notify_skip(f"no_change: monitor {monitor_index}")

    async def _attempt_recovery(self) -> None:
        """Attempt to recover from capture errors by recreating components.
        
        This handles cases where the underlying capture system (e.g., Wayland grim)
        gets into a bad state due to GDBus errors or other issues.
        """
        try:
            logger.info("Recovery: Recreating screen capture component")
            # Recreate the screen capture component to clear any bad state
            old_capture = self._screen_capture
            self._screen_capture = ScreenCapture(jpeg_quality=self.config.jpeg_quality)
            del old_capture
            
            # Reset error counters
            self._consecutive_errors = 0
            
            # Wait a moment before resuming
            await asyncio.sleep(2.0)
            
            logger.info("Recovery complete, resuming capture loop")
        except Exception as e:
            logger.error("Recovery failed: %s", e, exc_info=True)

    def pause(self) -> None:
        """Pause the capture loop."""
        self._set_state(CaptureState.PAUSED)

    def resume(self) -> None:
        """Resume the capture loop."""
        if self._state == CaptureState.PAUSED:
            self._set_state(CaptureState.RUNNING)

    def stop(self) -> None:
        """Stop the capture loop."""
        self._set_state(CaptureState.STOPPED)
        self._idle_detector.stop()
