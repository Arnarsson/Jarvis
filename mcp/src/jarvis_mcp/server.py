"""Jarvis MCP Server - Memory tools for Claude Code.

CRITICAL: structlog must be configured to write to stderr ONLY before any
other imports that might log. This is essential for stdio transport - any
stdout output breaks the JSON-RPC protocol.
"""

import sys

# Configure structlog to stderr BEFORE any other imports
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

# Now safe to import other modules
from mcp.server.fastmcp import FastMCP

# Create the MCP server instance
mcp = FastMCP(name="jarvis-memory")

# Register tools by importing (decorators register with mcp instance)
from jarvis_mcp.tools import search  # noqa: F401 E402
from jarvis_mcp.tools import catchup  # noqa: F401 E402
from jarvis_mcp.tools import calendar  # noqa: F401 E402
from jarvis_mcp.tools import meetings  # noqa: F401 E402
from jarvis_mcp.tools import email  # noqa: F401 E402
from jarvis_mcp.tools import workflow  # noqa: F401 E402

logger = structlog.get_logger()


def main() -> None:
    """Run the MCP server with stdio transport."""
    logger.info("mcp_server_starting", name="jarvis-memory", transport="stdio")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
