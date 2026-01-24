"""Change detection using perceptual hashing for efficient capture decisions."""

import time

import imagehash
from PIL import Image


class ChangeDetector:
    """Detects meaningful changes in screenshots using perceptual hashing.

    Implements hybrid trigger logic: captures on content change OR when
    minimum interval has elapsed, ensuring both responsiveness to changes
    and periodic baseline captures.
    """

    def __init__(self, hash_threshold: int = 5, min_interval: float = 15.0):
        """Initialize change detector.

        Args:
            hash_threshold: Hamming distance threshold. Images with distance
                           below this are considered similar (no change).
            min_interval: Minimum seconds between captures, regardless of
                         content changes. Ensures periodic baseline captures.
        """
        self.hash_threshold = hash_threshold
        self.min_interval = min_interval
        self.last_hashes: dict[int, imagehash.ImageHash] = {}
        self.last_capture_times: dict[int, float] = {}

    def should_capture(self, monitor_index: int, img: Image.Image) -> tuple[bool, str]:
        """Determine if a capture should be recorded.

        Args:
            monitor_index: Index of the monitor being evaluated
            img: Current screenshot as PIL Image

        Returns:
            Tuple of (should_capture, reason) where reason is one of:
            - "first_capture": No previous capture for this monitor
            - "interval_elapsed": Minimum interval has passed
            - "content_changed": Significant visual change detected
            - "no_change": Image is similar and interval not elapsed
        """
        now = time.monotonic()

        # First capture for this monitor
        if monitor_index not in self.last_hashes:
            return (True, "first_capture")

        # Check if minimum interval has elapsed
        elapsed = now - self.last_capture_times.get(monitor_index, 0)
        if elapsed >= self.min_interval:
            return (True, "interval_elapsed")

        # Compute perceptual hash of current image
        current_hash = imagehash.dhash(img)
        last_hash = self.last_hashes[monitor_index]

        # Calculate hamming distance (number of differing bits)
        distance = current_hash - last_hash

        # Content changed if distance exceeds threshold
        if distance > self.hash_threshold:
            return (True, "content_changed")

        return (False, "no_change")

    def record_capture(self, monitor_index: int, img: Image.Image) -> None:
        """Record that a capture was made.

        Updates the stored hash and timestamp for the given monitor.
        Call this after deciding to capture and successfully storing.

        Args:
            monitor_index: Index of the monitor that was captured
            img: The captured image
        """
        self.last_hashes[monitor_index] = imagehash.dhash(img)
        self.last_capture_times[monitor_index] = time.monotonic()

    def reset(self) -> None:
        """Clear all stored hashes and timestamps.

        Useful when restarting capture or changing configuration.
        """
        self.last_hashes.clear()
        self.last_capture_times.clear()
