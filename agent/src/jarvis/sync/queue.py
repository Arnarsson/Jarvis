"""SQLite-backed persistent queue for offline capture uploads."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class QueuedCapture:
    """A capture waiting in the upload queue."""

    id: str
    filepath: str
    metadata_json: str
    created_at: datetime
    attempts: int
    last_attempt: datetime | None
    status: str  # "pending", "uploading", "failed"

    @property
    def metadata(self) -> dict:
        """Parse metadata JSON."""
        return json.loads(self.metadata_json)


class UploadQueue:
    """SQLite-backed persistent queue for offline capture uploads.

    Captures are queued locally when the server is unavailable, and
    uploaded when connectivity is restored. The queue persists across
    agent restarts.
    """

    MAX_ATTEMPTS = 5
    RETRY_BACKOFF_SECONDS = 60  # Wait at least 60 seconds between retries

    def __init__(self, db_path: Path) -> None:
        """Initialize the upload queue.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        """Create the queue table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS upload_queue (
                id TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                last_attempt TEXT,
                status TEXT DEFAULT 'pending',
                error TEXT
            )
        """)
        # Index for efficient pending item queries
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_status_created
            ON upload_queue (status, created_at)
        """)
        self._conn.commit()

    def enqueue(self, filepath: Path, metadata: dict) -> str:
        """Add a capture to the upload queue.

        Args:
            filepath: Path to the capture file
            metadata: Metadata dictionary for the capture

        Returns:
            Queue item ID (UUID)
        """
        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        self._conn.execute(
            """
            INSERT INTO upload_queue (id, filepath, metadata_json, created_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (item_id, str(filepath), json.dumps(metadata), now),
        )
        self._conn.commit()
        return item_id

    def get_pending(self, limit: int = 10) -> list[QueuedCapture]:
        """Get pending items ready for upload.

        Returns items that are pending and haven't been attempted
        within the backoff period.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of QueuedCapture objects ordered by creation time
        """
        # Calculate the minimum time for retry
        backoff_cutoff = (
            datetime.utcnow() - timedelta(seconds=self.RETRY_BACKOFF_SECONDS)
        ).isoformat()

        cursor = self._conn.execute(
            """
            SELECT id, filepath, metadata_json, created_at, attempts, last_attempt, status
            FROM upload_queue
            WHERE status = 'pending'
              AND (last_attempt IS NULL OR last_attempt < ?)
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (backoff_cutoff, limit),
        )

        items = []
        for row in cursor.fetchall():
            items.append(
                QueuedCapture(
                    id=row["id"],
                    filepath=row["filepath"],
                    metadata_json=row["metadata_json"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    attempts=row["attempts"],
                    last_attempt=(
                        datetime.fromisoformat(row["last_attempt"])
                        if row["last_attempt"]
                        else None
                    ),
                    status=row["status"],
                )
            )
        return items

    def mark_uploading(self, item_id: str) -> None:
        """Mark an item as currently being uploaded.

        Args:
            item_id: Queue item ID
        """
        now = datetime.utcnow().isoformat()
        self._conn.execute(
            """
            UPDATE upload_queue
            SET status = 'uploading',
                attempts = attempts + 1,
                last_attempt = ?
            WHERE id = ?
            """,
            (now, item_id),
        )
        self._conn.commit()

    def mark_completed(self, item_id: str) -> None:
        """Remove an item from the queue after successful upload.

        Args:
            item_id: Queue item ID
        """
        self._conn.execute(
            "DELETE FROM upload_queue WHERE id = ?",
            (item_id,),
        )
        self._conn.commit()

    def mark_failed(self, item_id: str, error: str) -> None:
        """Mark an item as failed or return to pending for retry.

        If the item has reached max attempts, it's marked as 'failed'.
        Otherwise, it's returned to 'pending' for retry.

        Args:
            item_id: Queue item ID
            error: Error message from the failed upload
        """
        # Check current attempts
        cursor = self._conn.execute(
            "SELECT attempts FROM upload_queue WHERE id = ?",
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            return

        if row["attempts"] >= self.MAX_ATTEMPTS:
            # Mark as permanently failed
            self._conn.execute(
                """
                UPDATE upload_queue
                SET status = 'failed', error = ?
                WHERE id = ?
                """,
                (error, item_id),
            )
        else:
            # Return to pending for retry
            self._conn.execute(
                """
                UPDATE upload_queue
                SET status = 'pending', error = ?
                WHERE id = ?
                """,
                (error, item_id),
            )
        self._conn.commit()

    def get_stats(self) -> dict[str, int]:
        """Get queue statistics.

        Returns:
            Dictionary with counts by status
        """
        cursor = self._conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM upload_queue
            GROUP BY status
            """
        )

        stats = {"pending": 0, "uploading": 0, "failed": 0, "total": 0}
        for row in cursor.fetchall():
            stats[row["status"]] = row["count"]
            stats["total"] += row["count"]

        return stats

    def cleanup_old(self, days: int = 7) -> int:
        """Remove failed items older than N days.

        Args:
            days: Number of days after which to remove failed items

        Returns:
            Number of items removed
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor = self._conn.execute(
            """
            DELETE FROM upload_queue
            WHERE status = 'failed' AND created_at < ?
            """,
            (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
