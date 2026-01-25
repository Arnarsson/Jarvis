"""Web UI module for Jarvis server.

Provides HTML page routes and HTMX API endpoints.
"""

from jarvis_server.web.routes import router

__all__ = ["router"]
