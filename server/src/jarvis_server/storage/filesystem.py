"""Async filesystem storage for capture images.

Provides date-partitioned storage structure for easy management and archival.
All file I/O operations are async using aiofiles.
"""

import os
from datetime import datetime
from pathlib import Path

import aiofiles
import aiofiles.os


class FileStorage:
    """Async file storage with date-partitioned directory structure.

    Files are stored in: {base_path}/{YYYY}/{MM}/{DD}/{capture_id}.jpg

    This structure enables:
    - Easy cleanup of old captures by date
    - Efficient backup of specific time ranges
    - Natural organization for browsing
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize file storage.

        Args:
            base_path: Root directory for file storage.
                       Will be created if it doesn't exist.
        """
        self.base_path = Path(base_path)
        # Create base path synchronously on init (one-time operation)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store(
        self, capture_id: str, data: bytes, timestamp: datetime
    ) -> Path:
        """Store capture data to filesystem.

        Args:
            capture_id: Unique identifier for the capture (UUID string).
            data: Image bytes to store.
            timestamp: Capture timestamp for directory partitioning.

        Returns:
            Full path to the stored file.
        """
        # Build date-partitioned path
        date_path = self.base_path / timestamp.strftime("%Y/%m/%d")

        # Create date directories if needed
        await aiofiles.os.makedirs(date_path, exist_ok=True)

        # Full file path
        filepath = date_path / f"{capture_id}.jpg"

        # Write file asynchronously
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(data)

        return filepath

    async def retrieve(self, filepath: Path) -> bytes:
        """Retrieve capture data from filesystem.

        Args:
            filepath: Path to the file to retrieve.

        Returns:
            File contents as bytes.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        async with aiofiles.open(filepath, "rb") as f:
            return await f.read()

    async def delete(self, filepath: Path) -> bool:
        """Delete a capture file from filesystem.

        Args:
            filepath: Path to the file to delete.

        Returns:
            True if file was deleted, False if file did not exist.
        """
        filepath = Path(filepath)

        try:
            await aiofiles.os.remove(filepath)
            return True
        except FileNotFoundError:
            return False

    def get_storage_stats(self) -> dict:
        """Get storage statistics.

        This is synchronous since it's typically used for monitoring
        and admin purposes, not in the hot path.

        Returns:
            Dictionary with:
            - total_files: Number of files in storage
            - total_size_mb: Total size in megabytes
        """
        total_files = 0
        total_size = 0

        for root, _dirs, files in os.walk(self.base_path):
            for file in files:
                if file.endswith(".jpg"):
                    filepath = Path(root) / file
                    total_files += 1
                    total_size += filepath.stat().st_size

        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def get_path_for_capture(self, capture_id: str, timestamp: datetime) -> Path:
        """Get the expected path for a capture without storing.

        Useful for determining where a file would be stored.

        Args:
            capture_id: Capture UUID string.
            timestamp: Capture timestamp.

        Returns:
            Expected file path.
        """
        date_path = self.base_path / timestamp.strftime("%Y/%m/%d")
        return date_path / f"{capture_id}.jpg"
