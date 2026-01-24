"""Capture module - screenshot capture and change detection."""

from jarvis.capture.change import ChangeDetector
from jarvis.capture.screenshot import ScreenCapture, compress_to_jpeg

__all__ = ["ChangeDetector", "ScreenCapture", "compress_to_jpeg"]
