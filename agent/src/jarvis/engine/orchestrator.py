"""Capture orchestrator coordinating capture loop, storage, and upload."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from jarvis.config import Settings
from jarvis.engine.capture_loop import CaptureLoop, CaptureResult, CaptureState
from jarvis.meeting.detector import MeetingDetector, MeetingState
from jarvis.monitor import WindowMonitor
from jarvis.sync import CaptureUploader, UploadQueue

logger = logging.getLogger(__name__)


class CaptureOrchestrator:
    """High-level orchestrator for the capture system.

    Coordinates the CaptureLoop, local storage, and upload queue into
    a unified system. This is the main entry point that CLI and tray
    applications will use.

    Example:
        orchestrator = CaptureOrchestrator(settings)
        await orchestrator.start()
        # ... run until stopped ...
        await orchestrator.stop()
    """

    def __init__(self, config: Settings) -> None:
        """Initialize the capture orchestrator.

        Args:
            config: Settings instance with all configuration
        """
        self.config = config
        self._log = logger

        # Create data directories
        self._captures_dir = config.data_path / "captures"
        self._captures_dir.mkdir(parents=True, exist_ok=True)

        # Create components
        self._capture_loop = CaptureLoop(config)
        self._upload_queue = UploadQueue(config.data_path / "queue.db")
        self._uploader = CaptureUploader(
            server_url=config.server_url,
            max_retries=3,
            timeout=30.0,
        )

        # Meeting detection
        self._window_monitor = WindowMonitor()
        self._meeting_detector = MeetingDetector()
        self._current_meeting_id: str | None = None

        # State tracking
        self._running = False
        self._upload_task: asyncio.Task | None = None
        self._meeting_task: asyncio.Task | None = None
        self._last_capture_time: datetime | None = None
        self._capture_count = 0

    @property
    def state(self) -> CaptureState:
        """Get current capture loop state."""
        return self._capture_loop.state

    @property
    def is_paused(self) -> bool:
        """Check if capture is paused."""
        return self._capture_loop.state == CaptureState.PAUSED

    @property
    def queue_size(self) -> int:
        """Get number of items in upload queue."""
        stats = self._upload_queue.get_stats()
        return stats.get("pending", 0) + stats.get("uploading", 0)

    async def start(self) -> None:
        """Start the capture orchestrator.

        Wires up callbacks, starts the background upload worker,
        and starts the capture loop.
        """
        if self._running:
            return

        self._running = True

        # Wire up callbacks
        self._capture_loop.on_capture(self._handle_capture)
        self._capture_loop.on_skip(self._handle_skip)
        self._capture_loop.on_state_change(self._handle_state_change)

        self._log.info("Starting capture orchestrator, data_dir=%s", self.config.data_path)

        # Start background upload worker
        self._upload_task = asyncio.create_task(self._upload_worker())

        # Start meeting detection worker
        self._meeting_task = asyncio.create_task(self._meeting_worker())

        # Start capture loop (blocks until stopped)
        await self._capture_loop.start()

    def _handle_capture(self, result: CaptureResult) -> None:
        """Handle a capture event.

        Saves the capture locally and queues for upload.
        """
        try:
            # Generate dated path: {YYYY}/{MM}/{DD}/{timestamp}_{monitor}.jpg
            now = result.timestamp
            dated_dir = self._captures_dir / now.strftime("%Y/%m/%d")
            dated_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{now.strftime('%H%M%S')}_{result.monitor_index}.jpg"
            filepath = dated_dir / filename

            # Save capture locally
            with open(filepath, "wb") as f:
                f.write(result.jpeg_bytes)

            # Create metadata
            metadata = {
                "monitor_index": result.monitor_index,
                "timestamp": result.timestamp.isoformat(),
                "reason": result.reason,
                "width": result.image.width,
                "height": result.image.height,
            }

            # Enqueue for upload
            queue_id = self._upload_queue.enqueue(filepath, metadata)

            # Update tracking
            self._last_capture_time = result.timestamp
            self._capture_count += 1

            self._log.debug(
                "Capture saved: filepath=%s, queue_id=%s, reason=%s, size=%d",
                filepath, queue_id, result.reason, len(result.jpeg_bytes)
            )

        except Exception as e:
            self._log.error("Capture save failed: %s", e)

    def _handle_skip(self, reason: str) -> None:
        """Handle a skip event."""
        self._log.debug("Capture skipped: reason=%s", reason)

    def _handle_state_change(self, new_state: CaptureState) -> None:
        """Handle state change event."""
        self._log.info("Capture state changed: state=%s", new_state.value)

    async def _upload_worker(self) -> None:
        """Background worker that processes the upload queue.

        Runs in a loop, processing pending uploads and sleeping
        between batches.
        """
        while self._running:
            try:
                # Get pending items
                pending = self._upload_queue.get_pending(limit=10)

                for item in pending:
                    if not self._running:
                        break

                    filepath = Path(item.filepath)
                    if not filepath.exists():
                        # File was deleted, remove from queue
                        self._upload_queue.mark_completed(item.id)
                        continue

                    # Mark as uploading
                    self._upload_queue.mark_uploading(item.id)

                    # Try upload
                    result = await self._uploader.upload(filepath, item.metadata)

                    if result.success:
                        self._upload_queue.mark_completed(item.id)
                        self._log.debug(
                            "Upload success: queue_id=%s, capture_id=%s",
                            item.id, result.capture_id
                        )
                    else:
                        self._upload_queue.mark_failed(item.id, result.error or "Unknown error")
                        self._log.warning(
                            "Upload failed: queue_id=%s, error=%s, attempts=%d",
                            item.id, result.error, item.attempts + 1
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("Upload worker error: %s", e)

            # Sleep between batches
            await asyncio.sleep(5.0)

    async def _meeting_worker(self) -> None:
        """Background worker that checks for meeting state changes.

        Monitors window titles to detect meeting start/end and reports
        to the server.
        """
        while self._running:
            try:
                # Get current window info
                window = self._window_monitor.get_active_window()
                if window:
                    # Check for meeting state change
                    prev_in_meeting = self._meeting_detector.current_state.in_meeting
                    meeting_state = self._meeting_detector.check_window(
                        window.app_name,
                        window.window_title,
                    )

                    if meeting_state.in_meeting and not prev_in_meeting:
                        # Meeting just started
                        await self._report_meeting_start(meeting_state)
                    elif not meeting_state.in_meeting and prev_in_meeting:
                        # Meeting just ended
                        await self._report_meeting_end()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("Meeting worker error: %s", e)

            # Check every 2 seconds (less frequent than capture tick)
            await asyncio.sleep(2.0)

    async def _report_meeting_start(self, state: MeetingState) -> None:
        """Report meeting start to server."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.server_url}/api/meetings/start",
                    json={
                        "platform": state.platform.value if state.platform else None,
                        "window_title": state.window_title,
                        "detected_at": (
                            state.started_at.isoformat() if state.started_at else None
                        ),
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                self._current_meeting_id = data["id"]
                self._log.info(
                    "Meeting reported to server: meeting_id=%s", self._current_meeting_id
                )
        except Exception as e:
            self._log.error("Meeting report failed: %s", str(e))

    async def _report_meeting_end(self) -> None:
        """Report meeting end to server."""
        if not self._current_meeting_id:
            return

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.server_url}/api/meetings/end",
                    json={
                        "meeting_id": self._current_meeting_id,
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                self._log.info(
                    "Meeting end reported: meeting_id=%s", self._current_meeting_id
                )
                self._current_meeting_id = None
        except Exception as e:
            self._log.error("Meeting end report failed: %s", str(e))

    def pause(self) -> None:
        """Pause capture loop."""
        self._capture_loop.pause()

    def resume(self) -> None:
        """Resume capture loop."""
        self._capture_loop.resume()

    async def stop(self) -> None:
        """Stop the orchestrator gracefully.

        Stops the capture loop and upload worker, closes resources.
        """
        self._running = False

        # Stop capture loop
        self._capture_loop.stop()

        # Cancel upload worker
        if self._upload_task and not self._upload_task.done():
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass

        # Cancel meeting worker
        if self._meeting_task and not self._meeting_task.done():
            self._meeting_task.cancel()
            try:
                await self._meeting_task
            except asyncio.CancelledError:
                pass

        # Close resources
        await self._uploader.close()
        self._upload_queue.close()

        self._log.info("Capture orchestrator stopped, total_captures=%d", self._capture_count)

    def force_sync(self) -> None:
        """Trigger immediate upload attempt.

        Wakes up the upload worker to process pending items.
        Note: Currently a no-op as the worker runs on a fixed interval.
        Future: Could use an asyncio.Event to wake the worker.
        """
        # The upload worker will pick up pending items on next iteration
        self._log.debug("Force sync requested")

    def get_status(self) -> dict[str, Any]:
        """Get current orchestrator status.

        Returns:
            Dictionary with current state, queue stats, and capture info
        """
        queue_stats = self._upload_queue.get_stats()

        meeting_state = self._meeting_detector.current_state

        # Get last capture time from capture loop watchdog
        loop_last_capture = self._capture_loop.last_capture_time

        return {
            "state": self._capture_loop.state.value,
            "is_paused": self.is_paused,
            "running": self._running,
            "last_capture": (
                self._last_capture_time.isoformat()
                if self._last_capture_time
                else None
            ),
            "last_capture_loop": (
                loop_last_capture.isoformat()
                if loop_last_capture
                else None
            ),
            "capture_count": self._capture_count,
            "queue": {
                "pending": queue_stats.get("pending", 0),
                "uploading": queue_stats.get("uploading", 0),
                "failed": queue_stats.get("failed", 0),
                "total": queue_stats.get("total", 0),
            },
            "meeting": {
                "in_meeting": meeting_state.in_meeting,
                "platform": (
                    meeting_state.platform.value if meeting_state.platform else None
                ),
                "meeting_id": self._current_meeting_id,
            },
            "data_dir": str(self.config.data_path),
        }
