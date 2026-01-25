"""Async HTTP client for Jarvis server API."""

import os
from functools import lru_cache

import httpx

# Configuration
JARVIS_API_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:8000")
TIMEOUT_SECONDS = 25.0  # Leave margin for MCP 30s timeout

# Singleton client instance
_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    """Get or create the singleton HTTP client.

    Uses lazy initialization to create the client on first use.
    The client is configured with:
    - Connection pooling for efficiency
    - 25 second timeout (margin for MCP's 30s timeout)
    - JSON content type header
    """
    global _client

    if _client is None:
        _client = httpx.AsyncClient(
            base_url=JARVIS_API_URL,
            timeout=httpx.Timeout(TIMEOUT_SECONDS),
            headers={"Content-Type": "application/json"},
        )

    return _client


async def close_client() -> None:
    """Close the HTTP client and release resources."""
    global _client

    if _client is not None:
        await _client.aclose()
        _client = None
