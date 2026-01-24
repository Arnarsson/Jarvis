"""API endpoints for Jarvis server."""

from jarvis_server.api.captures import router as captures_router
from jarvis_server.api.health import router as health_router

__all__ = ["captures_router", "health_router"]
