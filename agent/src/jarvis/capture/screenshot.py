"""Multi-monitor screenshot capture with X11 and Wayland support."""

import os
import shutil
import subprocess
import tempfile
from io import BytesIO

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


def _is_wayland() -> bool:
    """Check if running on Wayland."""
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or "WAYLAND_DISPLAY" in os.environ


def _has_grim() -> bool:
    """Check if grim is available for Wayland screenshots."""
    return shutil.which("grim") is not None


class ScreenCapture:
    """Captures screenshots from monitors.

    Automatically detects X11 vs Wayland and uses appropriate backend:
    - X11: Uses mss library for fast capture
    - Wayland: Uses grim command-line tool

    Provides high-performance multi-monitor screenshot capture with
    JPEG compression for efficient storage.
    """

    def __init__(self, jpeg_quality: int = 80):
        """Initialize screen capture.

        Args:
            jpeg_quality: JPEG compression quality (1-100)
        """
        self.jpeg_quality = jpeg_quality
        self._use_wayland = _is_wayland() and _has_grim()

    def get_monitors(self) -> list[dict]:
        """Get list of monitor geometries.

        Returns:
            List of monitor dicts with keys: left, top, width, height
        """
        if self._use_wayland:
            # On Wayland, grim captures all outputs at once
            # Return a single "virtual" monitor representing full capture
            return [{"left": 0, "top": 0, "width": 0, "height": 0}]
        else:
            import mss
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
            RuntimeError: If capture fails
        """
        if self._use_wayland:
            return self._capture_wayland()
        else:
            return self._capture_x11(monitor_index)

    def _capture_wayland(self) -> tuple[Image.Image, bytes]:
        """Capture screenshot using grim on Wayland with GDBus error handling."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmpfile = f.name

        try:
            # Use grim to capture to temp file with timeout and error handling
            result = subprocess.run(
                ["grim", "-t", "jpeg", "-q", str(self.jpeg_quality), tmpfile],
                capture_output=True,
                timeout=10,
                env={**os.environ, "G_MESSAGES_DEBUG": ""},  # Suppress GLib debug messages
            )
            
            # Check for common GDBus/Wayland errors in stderr
            stderr = result.stderr.decode() if result.stderr else ""
            if "GDBus.Error" in stderr or "org.freedesktop.portal" in stderr:
                # GDBus portal error - try to provide helpful context
                raise RuntimeError(
                    f"Wayland portal error (GDBus): {stderr.strip()}\n"
                    "This usually means the screen capture portal is unresponsive. "
                    "The capture loop will attempt recovery."
                )
            
            if result.returncode != 0:
                raise RuntimeError(f"grim failed (exit {result.returncode}): {stderr.strip()}")

            # Verify the file was created and has content
            if not os.path.exists(tmpfile) or os.path.getsize(tmpfile) == 0:
                raise RuntimeError(
                    "grim succeeded but produced no output file. "
                    "This may indicate a Wayland compositor issue."
                )

            # Load the captured image
            img = Image.open(tmpfile)
            img.load()  # Force load before we delete the file

            # Read JPEG bytes
            with open(tmpfile, "rb") as f:
                jpeg_bytes = f.read()

            return img, jpeg_bytes
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "grim timed out after 10 seconds. "
                "This usually indicates a Wayland compositor hang or GDBus issue."
            )
        finally:
            # Clean up temp file
            try:
                os.unlink(tmpfile)
            except OSError:
                pass

    def _capture_x11(self, monitor_index: int) -> tuple[Image.Image, bytes]:
        """Capture screenshot using mss on X11."""
        import mss
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
