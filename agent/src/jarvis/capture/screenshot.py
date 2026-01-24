"""Multi-monitor screenshot capture using mss library."""

from io import BytesIO

import mss
from PIL import Image


def compress_to_jpeg(img: Image.Image, quality: int = 80) -> bytes:
    """Compress PIL Image to JPEG bytes.

    Args:
        img: PIL Image to compress
        quality: JPEG quality (1-100), default 80 for good balance

    Returns:
        JPEG image as bytes
    """
    buffer = BytesIO()
    img.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return buffer.getvalue()


class ScreenCapture:
    """Captures screenshots from monitors using mss.

    Provides high-performance multi-monitor screenshot capture with
    JPEG compression for efficient storage.
    """

    def __init__(self, jpeg_quality: int = 80):
        """Initialize screen capture.

        Args:
            jpeg_quality: JPEG compression quality (1-100)
        """
        self.jpeg_quality = jpeg_quality

    def get_monitors(self) -> list[dict]:
        """Get list of monitor geometries.

        Returns:
            List of monitor dicts with keys: left, top, width, height
            Note: Skips monitors[0] which is "all monitors combined"
        """
        with mss.mss() as sct:
            # monitors[0] is "all combined", monitors[1:] are individual
            return [dict(m) for m in sct.monitors[1:]]

    def capture_monitor(self, monitor_index: int) -> tuple[Image.Image, bytes]:
        """Capture a specific monitor.

        Args:
            monitor_index: Zero-based index (0 = primary monitor)

        Returns:
            Tuple of (PIL Image, JPEG bytes)

        Raises:
            IndexError: If monitor_index is out of range
        """
        with mss.mss() as sct:
            # monitors[0] is "all combined", so +1 for actual monitor
            monitors = sct.monitors[1:]
            if monitor_index >= len(monitors):
                raise IndexError(
                    f"Monitor index {monitor_index} out of range "
                    f"(have {len(monitors)} monitors)"
                )

            monitor = monitors[monitor_index]
            screenshot = sct.grab(monitor)

            # Convert BGRA to RGB PIL Image
            img = Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.bgra,
                "raw",
                "BGRX",
            )

            # Compress to JPEG
            jpeg_bytes = compress_to_jpeg(img, self.jpeg_quality)

            return img, jpeg_bytes

    def capture_active(self) -> list[tuple[int, Image.Image, bytes]]:
        """Capture the active/primary monitor.

        For now, captures only the primary monitor (index 0).
        Multi-monitor activity detection will be added in capture orchestrator.

        Returns:
            List of tuples: (monitor_index, PIL Image, JPEG bytes)
        """
        # Capture primary monitor only for now
        img, jpeg_bytes = self.capture_monitor(0)
        return [(0, img, jpeg_bytes)]
