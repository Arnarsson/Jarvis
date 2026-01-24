"""System tray interface for Jarvis desktop agent.

Provides visual status indication and quick access to common actions
(pause/resume, settings, force sync) via system tray.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import TYPE_CHECKING, Callable, Protocol

import pystray

from jarvis.icons import TrayStatus, create_status_icon

if TYPE_CHECKING:
    from pystray import Icon, MenuItem

logger = logging.getLogger(__name__)


class CaptureState(Enum):
    """Capture orchestrator states (mirrored from orchestrator)."""

    ACTIVE = "active"  # Actively capturing
    PAUSED = "paused"  # User-initiated pause
    IDLE = "idle"  # Auto-paused due to idle
    EXCLUDED = "excluded"  # Excluded app in foreground
    ERROR = "error"  # Error state
    SYNCING = "syncing"  # Syncing to server


class CaptureOrchestratorProtocol(Protocol):
    """Protocol defining what the tray expects from an orchestrator.

    The actual CaptureOrchestrator will implement this interface.
    This allows the tray to work with any compatible orchestrator.
    """

    def get_state(self) -> CaptureState:
        """Get current capture state."""
        ...

    def pause(self) -> None:
        """Pause capture."""
        ...

    def resume(self) -> None:
        """Resume capture."""
        ...

    def force_sync(self) -> None:
        """Force immediate sync to server."""
        ...

    def stop(self) -> None:
        """Stop the orchestrator."""
        ...

    def get_queue_stats(self) -> dict[str, int]:
        """Get upload queue statistics."""
        ...

    def register_state_callback(self, callback: Callable[[CaptureState], None]) -> None:
        """Register callback for state changes."""
        ...


# Map CaptureState to TrayStatus
STATE_TO_TRAY_STATUS: dict[CaptureState, TrayStatus] = {
    CaptureState.ACTIVE: TrayStatus.ACTIVE,
    CaptureState.PAUSED: TrayStatus.PAUSED,
    CaptureState.IDLE: TrayStatus.IDLE,
    CaptureState.EXCLUDED: TrayStatus.EXCLUDED,
    CaptureState.ERROR: TrayStatus.ERROR,
    CaptureState.SYNCING: TrayStatus.SYNCING,
}


class JarvisTray:
    """System tray interface for Jarvis desktop agent.

    Provides:
    - Visual status indication via icon color
    - Context menu for common actions
    - Integration with capture orchestrator

    Usage:
        orchestrator = CaptureOrchestrator(...)
        tray = JarvisTray(orchestrator)
        tray.run()  # Blocks - runs event loop
    """

    def __init__(self, orchestrator: CaptureOrchestratorProtocol | None = None) -> None:
        """Initialize the system tray.

        Args:
            orchestrator: Optional capture orchestrator to control.
                         If None, tray runs in standalone mode with limited functionality.
        """
        self._orchestrator = orchestrator
        self._status = TrayStatus.ACTIVE
        self._icon: Icon | None = None
        self._running = False

        # Register for orchestrator state changes
        if self._orchestrator is not None:
            try:
                self._orchestrator.register_state_callback(self._on_orchestrator_state_change)
            except (AttributeError, NotImplementedError):
                logger.warning("Orchestrator doesn't support state callbacks")

    @property
    def status(self) -> TrayStatus:
        """Current tray status."""
        return self._status

    def _get_orchestrator_state(self) -> CaptureState | None:
        """Get current state from orchestrator if available."""
        if self._orchestrator is None:
            return None
        try:
            return self._orchestrator.get_state()
        except (AttributeError, NotImplementedError):
            return None

    def _get_queue_pending(self) -> int:
        """Get number of pending items in upload queue."""
        if self._orchestrator is None:
            return 0
        try:
            stats = self._orchestrator.get_queue_stats()
            return stats.get("pending", 0)
        except (AttributeError, NotImplementedError):
            return 0

    def _is_active(self) -> bool:
        """Check if capture is currently active."""
        return self._status == TrayStatus.ACTIVE

    def _create_menu(self) -> pystray.Menu:
        """Create the context menu.

        Menu structure:
        - Pause/Resume Capture (dynamic)
        - ---
        - Open Settings... (placeholder)
        - View Recent Captures... (placeholder)
        - Force Sync Now
        - View Logs... (placeholder)
        - ---
        - Queue: N pending (status line)
        - ---
        - Quit Jarvis
        """
        pending = self._get_queue_pending()
        is_active = self._is_active()

        return pystray.Menu(
            # Toggle capture
            pystray.MenuItem(
                "Pause Capture" if is_active else "Resume Capture",
                self._on_toggle_capture,
            ),
            pystray.Menu.SEPARATOR,
            # Settings and views (placeholders for now)
            pystray.MenuItem(
                "Open Settings...",
                self._on_open_settings,
                enabled=False,  # Placeholder
            ),
            pystray.MenuItem(
                "View Recent Captures...",
                self._on_view_recent,
                enabled=False,  # Placeholder
            ),
            pystray.MenuItem(
                "Force Sync Now",
                self._on_force_sync,
                enabled=self._orchestrator is not None,
            ),
            pystray.MenuItem(
                "View Logs...",
                self._on_view_logs,
                enabled=False,  # Placeholder
            ),
            pystray.Menu.SEPARATOR,
            # Status line
            pystray.MenuItem(
                f"Queue: {pending} pending",
                None,  # No action - just informational
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            # Quit
            pystray.MenuItem("Quit Jarvis", self._on_quit),
        )

    def _on_toggle_capture(self, icon: Icon, item: MenuItem) -> None:
        """Handle pause/resume toggle."""
        if self._orchestrator is None:
            # Standalone mode - just toggle local status
            if self._status == TrayStatus.ACTIVE:
                self._update_status(TrayStatus.PAUSED)
            else:
                self._update_status(TrayStatus.ACTIVE)
            return

        # Control orchestrator
        try:
            if self._is_active():
                self._orchestrator.pause()
                logger.info("Capture paused via tray")
            else:
                self._orchestrator.resume()
                logger.info("Capture resumed via tray")
        except Exception as e:
            logger.error(f"Failed to toggle capture: {e}")
            self._update_status(TrayStatus.ERROR)

    def _on_force_sync(self, icon: Icon, item: MenuItem) -> None:
        """Handle force sync action."""
        if self._orchestrator is None:
            return

        try:
            # Show syncing status briefly
            self._update_status(TrayStatus.SYNCING)
            self._orchestrator.force_sync()
            logger.info("Force sync triggered via tray")
            # Status will be updated by orchestrator callback
        except Exception as e:
            logger.error(f"Failed to force sync: {e}")
            self._update_status(TrayStatus.ERROR)

    def _on_open_settings(self, icon: Icon, item: MenuItem) -> None:
        """Handle open settings action (placeholder)."""
        logger.info("Settings action triggered (not yet implemented)")

    def _on_view_recent(self, icon: Icon, item: MenuItem) -> None:
        """Handle view recent captures action (placeholder)."""
        logger.info("View recent action triggered (not yet implemented)")

    def _on_view_logs(self, icon: Icon, item: MenuItem) -> None:
        """Handle view logs action (placeholder)."""
        logger.info("View logs action triggered (not yet implemented)")

    def _on_quit(self, icon: Icon, item: MenuItem) -> None:
        """Handle quit action."""
        logger.info("Quit requested via tray")
        self._running = False

        # Stop orchestrator if available
        if self._orchestrator is not None:
            try:
                self._orchestrator.stop()
            except Exception as e:
                logger.error(f"Error stopping orchestrator: {e}")

        # Stop the tray icon
        if self._icon is not None:
            self._icon.stop()

    def _update_status(self, new_status: TrayStatus) -> None:
        """Update the tray status and icon.

        Args:
            new_status: The new status to display.
        """
        if new_status == self._status and self._icon is not None:
            return  # No change needed

        self._status = new_status
        logger.debug(f"Tray status changed to {new_status.value}")

        if self._icon is not None:
            # Update icon image
            self._icon.icon = create_status_icon(new_status)
            # Update menu (menu is regenerated on each show, but update title)
            self._icon.title = f"Jarvis - {new_status.value.capitalize()}"

    def _on_orchestrator_state_change(self, state: CaptureState) -> None:
        """Handle state change from orchestrator.

        Args:
            state: The new capture state.
        """
        tray_status = STATE_TO_TRAY_STATUS.get(state, TrayStatus.ERROR)
        self._update_status(tray_status)

    def run(self) -> None:
        """Run the system tray (blocking).

        This method blocks and runs the tray event loop on the calling thread.
        On macOS, this should be called from the main thread.
        """
        self._running = True

        # Sync status with orchestrator if available
        state = self._get_orchestrator_state()
        if state is not None:
            self._status = STATE_TO_TRAY_STATUS.get(state, TrayStatus.ACTIVE)

        self._icon = pystray.Icon(
            name="jarvis",
            icon=create_status_icon(self._status),
            title=f"Jarvis - {self._status.value.capitalize()}",
            menu=self._create_menu(),
        )

        logger.info("Starting Jarvis system tray")
        self._icon.run()

    def run_detached(self) -> threading.Thread:
        """Run the system tray in a separate thread.

        Returns:
            The thread running the tray (can be joined for cleanup).

        Note:
            On macOS, this may have limitations due to AppKit requirements.
            Prefer run() from main thread on macOS.
        """
        thread = threading.Thread(target=self.run, daemon=True, name="jarvis-tray")
        thread.start()
        logger.info("Started Jarvis system tray in background thread")
        return thread

    def stop(self) -> None:
        """Stop the system tray.

        Can be called from any thread to stop the tray.
        """
        self._running = False
        if self._icon is not None:
            self._icon.stop()
