"""Async HTTP uploader for capture sync with retry logic."""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from jarvis import __version__


@dataclass
class UploadResult:
    """Result of an upload attempt."""

    success: bool
    capture_id: str | None = None
    error: str | None = None
    attempts: int = 0


class CaptureUploader:
    """Async HTTP uploader for captures with exponential backoff retry.

    Uses httpx.AsyncClient for connection pooling and efficient uploads.
    Retries on transient failures (5xx, connection errors) but not on
    client errors (4xx).
    """

    def __init__(
        self,
        server_url: str,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the uploader.

        Args:
            server_url: Base URL of the Jarvis server (e.g., http://localhost:8000)
            max_retries: Maximum number of retry attempts on transient failures
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.max_retries = max_retries
        self.timeout = timeout

        # Create reusable client with connection pooling
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": f"jarvis-agent/{__version__}",
            },
        )

    async def upload(self, filepath: Path, metadata: dict[str, Any]) -> UploadResult:
        """Upload a capture file to the server with retry.

        Args:
            filepath: Path to the capture file (e.g., JPEG screenshot)
            metadata: Metadata dictionary to send with the capture

        Returns:
            UploadResult with success status and capture ID or error
        """
        if not filepath.exists():
            return UploadResult(
                success=False,
                error=f"File not found: {filepath}",
                attempts=0,
            )

        attempt = 0
        last_error: str | None = None

        while attempt < self.max_retries:
            attempt += 1

            try:
                # Open file and create multipart form
                with open(filepath, "rb") as f:
                    files = {"file": (filepath.name, f, "image/jpeg")}
                    data = {"metadata": json.dumps(metadata)}

                    response = await self._client.post(
                        f"{self.server_url}/api/captures/",
                        files=files,
                        data=data,
                    )

                # Check response status
                if response.status_code == 200 or response.status_code == 201:
                    try:
                        result = response.json()
                        return UploadResult(
                            success=True,
                            capture_id=result.get("id"),
                            attempts=attempt,
                        )
                    except json.JSONDecodeError:
                        return UploadResult(
                            success=True,
                            capture_id=None,
                            attempts=attempt,
                        )

                # 4xx errors - don't retry (client error)
                if 400 <= response.status_code < 500:
                    return UploadResult(
                        success=False,
                        error=f"Client error: {response.status_code} - {response.text}",
                        attempts=attempt,
                    )

                # 5xx errors - retry with backoff
                last_error = f"Server error: {response.status_code}"

            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
            except httpx.HTTPError as e:
                last_error = f"HTTP error: {e}"

            # Exponential backoff before retry
            if attempt < self.max_retries:
                await asyncio.sleep(2**attempt)

        return UploadResult(
            success=False,
            error=last_error or "Max retries exceeded",
            attempts=attempt,
        )

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        metadata: dict[str, Any],
    ) -> UploadResult:
        """Upload capture bytes directly to the server with retry.

        Args:
            data: Raw bytes of the capture (e.g., JPEG data)
            filename: Filename to use in the upload
            metadata: Metadata dictionary to send with the capture

        Returns:
            UploadResult with success status and capture ID or error
        """
        attempt = 0
        last_error: str | None = None

        while attempt < self.max_retries:
            attempt += 1

            try:
                files = {"file": (filename, data, "image/jpeg")}
                form_data = {"metadata": json.dumps(metadata)}

                response = await self._client.post(
                    f"{self.server_url}/api/captures/",
                    files=files,
                    data=form_data,
                )

                # Check response status
                if response.status_code == 200 or response.status_code == 201:
                    try:
                        result = response.json()
                        return UploadResult(
                            success=True,
                            capture_id=result.get("id"),
                            attempts=attempt,
                        )
                    except json.JSONDecodeError:
                        return UploadResult(
                            success=True,
                            capture_id=None,
                            attempts=attempt,
                        )

                # 4xx errors - don't retry
                if 400 <= response.status_code < 500:
                    return UploadResult(
                        success=False,
                        error=f"Client error: {response.status_code} - {response.text}",
                        attempts=attempt,
                    )

                # 5xx errors - retry
                last_error = f"Server error: {response.status_code}"

            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
            except httpx.HTTPError as e:
                last_error = f"HTTP error: {e}"

            # Exponential backoff
            if attempt < self.max_retries:
                await asyncio.sleep(2**attempt)

        return UploadResult(
            success=False,
            error=last_error or "Max retries exceeded",
            attempts=attempt,
        )

    async def check_server(self) -> bool:
        """Check if the server is available.

        Returns:
            True if server responds to health check, False otherwise
        """
        try:
            response = await self._client.get(
                f"{self.server_url}/health/ready",
                timeout=httpx.Timeout(5.0),
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        await self._client.aclose()

    async def __aenter__(self) -> "CaptureUploader":
        """Enter async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager."""
        await self.close()
