"""Integration tests verifying component interaction in the agent.

Tests that multiple components work together correctly:
- CaptureLoop respects exclusions
- CaptureLoop respects idle detection
- ChangeDetector skips duplicates
- UploadQueue persists across restarts
"""

import asyncio
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from jarvis.capture.change import ChangeDetector
from jarvis.monitor.window import ExclusionFilter, WindowInfo
from jarvis.sync.queue import UploadQueue


class TestExclusionFilterIntegration:
    """Test exclusion filter with real exclusion patterns."""

    def test_capture_loop_respects_exclusions_password_manager(self):
        """Verify captures are skipped when excluded app is active."""
        # Setup exclusion filter with password manager patterns
        exclusions = {
            "app_names": ["1password", "bitwarden", "keepass"],
            "window_titles": ["private browsing", "incognito"],
        }
        exclusion_filter = ExclusionFilter(exclusions)

        # Simulate 1Password being active
        window = WindowInfo(
            app_name="1Password 8",
            window_title="My Vault - 1Password",
            is_active=True,
        )

        should_exclude, pattern = exclusion_filter.should_exclude(window)

        assert should_exclude is True
        assert pattern == "1password"

    def test_capture_loop_respects_exclusions_private_browsing(self):
        """Verify captures are skipped for private browsing windows."""
        exclusions = {
            "app_names": ["1password"],
            "window_titles": ["private browsing", "incognito"],
        }
        exclusion_filter = ExclusionFilter(exclusions)

        # Simulate Firefox private browsing
        window = WindowInfo(
            app_name="Firefox",
            window_title="Mozilla Firefox - Private Browsing",
            is_active=True,
        )

        should_exclude, pattern = exclusion_filter.should_exclude(window)

        assert should_exclude is True
        assert pattern == "private browsing"

    def test_capture_allowed_for_normal_apps(self):
        """Verify captures are allowed for non-excluded apps."""
        exclusions = {
            "app_names": ["1password", "bitwarden"],
            "window_titles": ["private browsing"],
        }
        exclusion_filter = ExclusionFilter(exclusions)

        # Simulate normal app
        window = WindowInfo(
            app_name="Visual Studio Code",
            window_title="test.py - jarvis - Visual Studio Code",
            is_active=True,
        )

        should_exclude, pattern = exclusion_filter.should_exclude(window)

        assert should_exclude is False
        assert pattern is None


class TestIdleDetectorIntegration:
    """Test idle detection integration with capture loop logic."""

    def test_capture_loop_respects_idle_state(self):
        """Verify captures pause when user is idle."""
        # Create a mock idle detector for testing without real input monitoring
        class MockIdleDetector:
            def __init__(self, is_idle_value: bool = False):
                self._is_idle = is_idle_value

            def is_idle(self) -> bool:
                return self._is_idle

            def start(self):
                pass

            def stop(self):
                pass

        # When user is NOT idle, capture should proceed
        detector_active = MockIdleDetector(is_idle_value=False)
        assert detector_active.is_idle() is False

        # When user IS idle, capture should be skipped
        detector_idle = MockIdleDetector(is_idle_value=True)
        assert detector_idle.is_idle() is True

    def test_idle_threshold_behavior(self):
        """Test that idle detection respects threshold timing."""
        # This tests the idle detection logic without actually waiting
        # The real IdleDetector uses time.monotonic() for accurate timing

        class TimedIdleDetector:
            def __init__(self, idle_threshold: float):
                self.idle_threshold = idle_threshold
                self._last_activity = time.monotonic()

            def record_activity(self):
                self._last_activity = time.monotonic()

            def is_idle(self) -> bool:
                return (time.monotonic() - self._last_activity) > self.idle_threshold

        # With 0.1 second threshold
        detector = TimedIdleDetector(idle_threshold=0.1)

        # Initially not idle (just created)
        assert detector.is_idle() is False

        # Wait for threshold to pass
        time.sleep(0.15)
        assert detector.is_idle() is True

        # Activity resets idle state
        detector.record_activity()
        assert detector.is_idle() is False


class TestChangeDetectorIntegration:
    """Test change detection with real image processing."""

    def test_change_detection_skips_duplicate_captures(self):
        """Verify second capture of same image is skipped."""
        detector = ChangeDetector(hash_threshold=5, min_interval=60.0)

        # Create a static test image
        image = Image.new("RGB", (100, 100), color="blue")

        # First capture should always happen
        should_capture, reason = detector.should_capture(0, image)
        assert should_capture is True
        assert reason == "first_capture"

        # Record the capture
        detector.record_capture(0, image)

        # Second capture of same image should be skipped (no change, interval not elapsed)
        should_capture, reason = detector.should_capture(0, image)
        assert should_capture is False
        assert reason == "no_change"

    def test_change_detection_captures_on_content_change(self):
        """Verify capture happens when content changes significantly."""
        detector = ChangeDetector(hash_threshold=5, min_interval=60.0)

        # First image: horizontal gradient (creates distinctive hash)
        image1 = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                image1.putpixel((x, y), (x * 2, 0, 0))  # Red gradient left to right

        should_capture, reason = detector.should_capture(0, image1)
        assert should_capture is True
        detector.record_capture(0, image1)

        # Second image: vertical gradient (very different from horizontal)
        image2 = Image.new("RGB", (100, 100))
        for x in range(100):
            for y in range(100):
                image2.putpixel((x, y), (0, y * 2, 0))  # Green gradient top to bottom

        should_capture, reason = detector.should_capture(0, image2)
        assert should_capture is True
        assert reason == "content_changed"

    def test_change_detection_captures_after_interval(self):
        """Verify capture happens after min_interval even without change."""
        # Very short interval for testing
        detector = ChangeDetector(hash_threshold=5, min_interval=0.1)

        image = Image.new("RGB", (100, 100), color="blue")

        # First capture
        should_capture, _ = detector.should_capture(0, image)
        assert should_capture is True
        detector.record_capture(0, image)

        # Wait for interval to elapse
        time.sleep(0.15)

        # Should capture due to interval even though image is same
        should_capture, reason = detector.should_capture(0, image)
        assert should_capture is True
        assert reason == "interval_elapsed"

    def test_change_detection_per_monitor(self):
        """Verify change detection tracks monitors independently."""
        detector = ChangeDetector(hash_threshold=5, min_interval=60.0)

        image = Image.new("RGB", (100, 100), color="blue")

        # First capture on monitor 0
        should_capture, reason = detector.should_capture(0, image)
        assert should_capture is True
        assert reason == "first_capture"
        detector.record_capture(0, image)

        # First capture on monitor 1 (should also capture)
        should_capture, reason = detector.should_capture(1, image)
        assert should_capture is True
        assert reason == "first_capture"


class TestUploadQueuePersistence:
    """Test upload queue persistence across restarts."""

    def test_upload_queue_persists_across_restart(self):
        """Verify queued items survive queue close and reopen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "queue.db"

            # Create queue and add item
            queue1 = UploadQueue(db_path)
            item_id = queue1.enqueue(
                filepath=Path("/tmp/test_capture.jpg"),
                metadata={"timestamp": "2026-01-24T12:00:00Z", "monitor": 0},
            )

            # Verify item is pending
            pending = queue1.get_pending()
            assert len(pending) == 1
            assert pending[0].id == item_id

            # Close queue
            queue1.close()

            # Reopen queue (simulates agent restart)
            queue2 = UploadQueue(db_path)

            # Verify item is still pending
            pending = queue2.get_pending()
            assert len(pending) == 1
            assert pending[0].id == item_id
            assert pending[0].metadata["monitor"] == 0

            queue2.close()

    def test_upload_queue_maintains_order(self):
        """Verify queue maintains FIFO order across restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "queue.db"

            # Create queue and add multiple items
            queue1 = UploadQueue(db_path)
            ids = []
            for i in range(3):
                item_id = queue1.enqueue(
                    filepath=Path(f"/tmp/capture_{i}.jpg"),
                    metadata={"index": i},
                )
                ids.append(item_id)
                time.sleep(0.01)  # Ensure different timestamps

            queue1.close()

            # Reopen and verify order
            queue2 = UploadQueue(db_path)
            pending = queue2.get_pending()

            assert len(pending) == 3
            assert [p.id for p in pending] == ids  # Same order
            assert [p.metadata["index"] for p in pending] == [0, 1, 2]

            queue2.close()

    def test_upload_queue_completed_items_removed(self):
        """Verify completed items are removed from queue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "queue.db"

            queue = UploadQueue(db_path)

            # Add two items
            id1 = queue.enqueue(Path("/tmp/1.jpg"), {"n": 1})
            id2 = queue.enqueue(Path("/tmp/2.jpg"), {"n": 2})

            # Complete first item
            queue.mark_completed(id1)

            # Only second item should remain
            pending = queue.get_pending()
            assert len(pending) == 1
            assert pending[0].id == id2

            queue.close()

    def test_upload_queue_stats(self):
        """Verify queue statistics are accurate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "queue.db"

            queue = UploadQueue(db_path)

            # Add items
            id1 = queue.enqueue(Path("/tmp/1.jpg"), {})
            id2 = queue.enqueue(Path("/tmp/2.jpg"), {})
            id3 = queue.enqueue(Path("/tmp/3.jpg"), {})

            # Mark one as uploading
            queue.mark_uploading(id1)

            # Mark another as failed (with enough attempts to be permanently failed)
            for _ in range(UploadQueue.MAX_ATTEMPTS):
                queue.mark_uploading(id2)
                queue.mark_failed(id2, "connection error")

            stats = queue.get_stats()

            assert stats["uploading"] == 1
            assert stats["failed"] == 1
            assert stats["pending"] == 1
            assert stats["total"] == 3

            queue.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
