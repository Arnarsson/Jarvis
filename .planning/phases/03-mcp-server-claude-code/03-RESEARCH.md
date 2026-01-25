# Phase 3: MCP Server & Claude Code - Research

**Researched:** 2026-01-25
**Domain:** MCP (Model Context Protocol) server implementation with Python SDK
**Confidence:** HIGH

## Summary

This phase implements an MCP server that exposes Jarvis memory search capabilities to Claude Code. The server provides two primary tools: `search_memory` for hybrid semantic/keyword search across all captured content, and `catch_me_up` for context recovery on topics/projects. The server connects via stdio transport (the standard for local MCP servers), logs all calls to an audit trail, and implements input validation to prevent prompt injection attacks.

The standard approach uses the official MCP Python SDK (mcp>=1.26.0) with the FastMCP high-level API for tool definitions. FastMCP uses decorators and type hints to automatically generate tool schemas, making it Pythonic and maintainable. The server calls the existing hybrid search infrastructure from Phase 2, wrapping those APIs in MCP-compatible tools.

**Primary recommendation:** Use `mcp[cli]>=1.26.0` with FastMCP decorators. Run as a separate Python module installed via pip, configured in Claude Code with `claude mcp add --transport stdio`. Implement Pydantic validators for input sanitization and structlog for audit logging.

## Standard Stack

The established libraries/tools for this domain:

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp[cli] | >=1.26.0 | MCP Python SDK with FastMCP | Official Anthropic SDK, stable v1.x production-ready |
| pydantic | 2.x | Input validation and schemas | FastMCP uses Pydantic internally, already in project |
| structlog | >=24.0 | Audit logging | Already used in jarvis-server, JSON output for production |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27.x | HTTP client for calling server APIs | Async calls to FastAPI search endpoint |
| typing-extensions | 4.x | Extended type hints | Required for MCP SDK type annotations |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastMCP | Low-level MCP Server | FastMCP preferred - cleaner decorators, less boilerplate |
| Separate process | In-process with server | Separate process required - stdio transport, cleaner separation |
| HTTP transport | stdio transport | stdio is standard for local MCP servers, simpler auth |

**Installation:**
```bash
pip install "mcp[cli]>=1.26.0,<2" httpx>=0.27
```

Note: Pin to `<2` to stay on stable v1.x. v2 is in development (Q1 2026) with potential breaking changes.

## Architecture Patterns

### Recommended Project Structure

```
mcp/
├── src/
│   └── jarvis_mcp/
│       ├── __init__.py
│       ├── server.py           # FastMCP server with tool definitions
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search.py       # search_memory tool implementation
│       │   └── catchup.py      # catch_me_up tool implementation
│       ├── validators.py       # Pydantic models for input validation
│       ├── audit.py            # Audit logging functions
│       └── client.py           # HTTP client for server API calls
├── pyproject.toml
└── tests/
```

### Pattern 1: FastMCP Tool Definition

**What:** Define MCP tools using Python decorators and type hints
**When to use:** All MCP tool implementations

```python
# Source: FastMCP documentation (gofastmcp.com/servers/tools)
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from typing import Annotated

mcp = FastMCP("jarvis-memory")

@mcp.tool()
async def search_memory(
    query: Annotated[str, Field(
        min_length=1,
        max_length=1000,
        description="Natural language search query"
    )],
    limit: Annotated[int, Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum results to return"
    )] = 10,
) -> str:
    """Search all Jarvis memory sources using semantic and keyword matching.

    Returns relevant captures, chat messages, and documents ordered by relevance.
    """
    # Validate and sanitize input
    sanitized_query = sanitize_input(query)

    # Call server API
    results = await client.search(sanitized_query, limit=limit)

    # Format for LLM consumption
    return format_search_results(results)
```

### Pattern 2: Stdio Transport Startup

**What:** Run MCP server with stdio transport for Claude Code integration
**When to use:** Main entry point for the MCP server

```python
# Source: MCP SDK documentation
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("jarvis-memory")

# Import and register tools
from jarvis_mcp.tools import search, catchup

def main():
    # CRITICAL: For stdio transport, never use print() or log to stdout
    # Configure structlog to write to stderr
    import sys
    import structlog
    structlog.configure(
        processors=[...],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )

    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

### Pattern 3: Input Sanitization for Prompt Injection Prevention

**What:** Validate and sanitize all user inputs before processing
**When to use:** All tool parameter handling

```python
# Source: OWASP MCP Top 10 + Pydantic best practices
from pydantic import BaseModel, Field, field_validator
import re

class SearchInput(BaseModel):
    """Validated search input with sanitization."""

    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Remove potential prompt injection patterns."""
        # Strip control characters
        v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)

        # Remove excessive whitespace but preserve structure
        v = ' '.join(v.split())

        # Don't allow markdown injection for tool instructions
        # These patterns could confuse the LLM about response format
        dangerous_patterns = [
            r'^```',           # Code block starts
            r'^\s*#',          # Markdown headers at start
            r'<\|.*?\|>',      # Common prompt delimiters
            r'\[INST\]',       # Instruction markers
            r'\[/INST\]',
        ]

        for pattern in dangerous_patterns:
            if re.match(pattern, v, re.IGNORECASE):
                # Log suspicious input attempt
                logger.warning(
                    "suspicious_input_blocked",
                    pattern=pattern,
                    input_preview=v[:50],
                )
                raise ValueError("Query contains invalid patterns")

        return v
```

### Pattern 4: Audit Logging for MCP Calls

**What:** Log all MCP tool invocations with structured data
**When to use:** Every tool call

```python
# Source: structlog best practices + OWASP MCP-08 (Lack of Audit)
import structlog
from datetime import datetime, timezone
from typing import Any

logger = structlog.get_logger("jarvis_mcp.audit")

def log_mcp_call(
    tool_name: str,
    input_params: dict[str, Any],
    result_summary: str,
    duration_ms: float,
    success: bool,
    error: str | None = None,
) -> None:
    """Log an MCP tool invocation for audit trail.

    Args:
        tool_name: Name of the invoked tool
        input_params: Sanitized input parameters (no secrets)
        result_summary: Brief summary of results (not full content)
        duration_ms: Execution time in milliseconds
        success: Whether the call succeeded
        error: Error message if failed (sanitized)
    """
    log_data = {
        "tool": tool_name,
        "params": _sanitize_for_log(input_params),
        "result_summary": result_summary[:200],  # Truncate for log size
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }

    if error:
        log_data["error"] = error[:500]  # Truncate errors too
        logger.error("mcp_tool_failed", **log_data)
    else:
        logger.info("mcp_tool_invoked", **log_data)

def _sanitize_for_log(params: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive data from params before logging."""
    sanitized = {}
    for key, value in params.items():
        if isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:100] + "...[truncated]"
        else:
            sanitized[key] = value
    return sanitized
```

### Pattern 5: Claude Code Configuration

**What:** Configure Claude Code to connect to the MCP server
**When to use:** Setting up Claude Code integration

```bash
# Source: Claude Code MCP documentation (code.claude.com/docs/en/mcp)

# Option 1: Add with scope (recommended for development)
claude mcp add --transport stdio --scope local jarvis-memory \
  -- python -m jarvis_mcp.server

# Option 2: With environment variables
claude mcp add --transport stdio --scope local \
  --env JARVIS_API_URL=http://127.0.0.1:8000 \
  jarvis-memory -- python -m jarvis_mcp.server

# Option 3: Using uv for dependency isolation
claude mcp add --transport stdio --scope local jarvis-memory \
  -- uv run --project /path/to/jarvis/mcp python -m jarvis_mcp.server

# Verify configuration
claude mcp list
claude mcp get jarvis-memory
```

### Anti-Patterns to Avoid

- **Logging to stdout in stdio transport:** NEVER use print() or log to stdout - breaks JSON-RPC protocol
- **Accepting arbitrary user input without validation:** Always sanitize for prompt injection
- **Returning raw error messages:** Mask internal errors, only expose ToolError messages
- **Skipping audit logging:** Every MCP call must be logged for security compliance
- **Hard-coding API URLs:** Use environment variables for server connection
- **Using `*args` or `**kwargs` in tools:** FastMCP cannot generate schemas for variable arguments

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol implementation | Custom JSON-RPC handler | MCP SDK | Complex spec, edge cases, version compatibility |
| Tool schema generation | Manual JSON schema | FastMCP decorators | Type hints + docstrings auto-generate schemas |
| Input validation | Regex-only sanitization | Pydantic validators | Composable, tested, handles edge cases |
| Transport handling | Raw stdin/stdout | mcp.run(transport="stdio") | Handles buffering, encoding, connection lifecycle |
| Error formatting | Custom error types | mcp.exceptions.ToolError | MCP-compliant error responses |

**Key insight:** The MCP SDK handles all the protocol complexity. Your job is just defining tools and calling your existing APIs.

## Common Pitfalls

### Pitfall 1: Stdout Pollution Breaking JSON-RPC

**What goes wrong:** MCP server returns malformed responses or hangs
**Why it happens:** print(), logging to stdout, or library that writes to stdout
**How to avoid:** Configure ALL loggers to write to stderr; grep codebase for `print(` statements
**Warning signs:** "Connection closed" errors in Claude Code, malformed JSON errors

### Pitfall 2: Prompt Injection via Search Queries

**What goes wrong:** Malicious search queries manipulate LLM behavior
**Why it happens:** Raw user input passed to search without sanitization
**How to avoid:** Pydantic validators strip control characters and dangerous patterns; log suspicious inputs
**Warning signs:** Search results containing instruction-like text, unexpected LLM behavior

### Pitfall 3: Missing Audit Trail

**What goes wrong:** Cannot investigate security incidents or usage patterns
**Why it happens:** Skipping logging in tool implementations
**How to avoid:** Wrap all tool calls with audit logging decorator/function
**Warning signs:** Empty audit logs, no way to trace MCP usage

### Pitfall 4: Synchronous Blocking Calls

**What goes wrong:** MCP server becomes unresponsive during long operations
**Why it happens:** Using sync HTTP calls instead of async
**How to avoid:** Use httpx async client for all server API calls; FastMCP handles sync in threadpool
**Warning signs:** Slow tool responses, timeouts in Claude Code

### Pitfall 5: Large Response Handling

**What goes wrong:** Claude Code warns about output exceeding 10,000 tokens
**Why it happens:** Returning too many search results or full document content
**How to avoid:** Limit results (max 10-20), truncate text previews (200 chars), summarize
**Warning signs:** Token limit warnings in Claude Code logs

### Pitfall 6: Error Message Information Leakage

**What goes wrong:** Internal errors expose system details to attackers
**Why it happens:** Returning raw exception messages
**How to avoid:** Use `mask_error_details=True` in FastMCP; only expose ToolError messages
**Warning signs:** Stack traces visible in tool responses, internal paths exposed

## Code Examples

### Complete MCP Server Setup

```python
# Source: MCP SDK + FastMCP documentation
# server.py
from mcp.server.fastmcp import FastMCP
from mcp.exceptions import ToolError
import structlog
import sys

# CRITICAL: Configure logging BEFORE importing anything that might log
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

logger = structlog.get_logger("jarvis_mcp")

# Create server with error masking for security
mcp = FastMCP(
    name="jarvis-memory",
    mask_error_details=True,  # Only ToolError messages reach clients
)

# Import tools after server is created
from jarvis_mcp.tools.search import search_memory
from jarvis_mcp.tools.catchup import catch_me_up

def main():
    logger.info("mcp_server_starting", transport="stdio")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

### search_memory Tool Implementation

```python
# Source: Based on Phase 2 search API + FastMCP patterns
# tools/search.py
from typing import Annotated
from pydantic import Field
import time
import httpx

from jarvis_mcp.server import mcp, logger
from jarvis_mcp.validators import validate_search_query
from jarvis_mcp.audit import log_mcp_call
from mcp.exceptions import ToolError

# Async HTTP client (reuse connection)
_client: httpx.AsyncClient | None = None

async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        import os
        base_url = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:8000")
        _client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
    return _client

@mcp.tool()
async def search_memory(
    query: Annotated[str, Field(
        min_length=1,
        max_length=1000,
        description="Natural language search query for finding information in your memory"
    )],
    limit: Annotated[int, Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )] = 10,
    sources: Annotated[list[str] | None, Field(
        default=None,
        description="Filter by source: screen, chatgpt, claude, grok"
    )] = None,
) -> str:
    """Search all Jarvis memory sources using semantic and keyword matching.

    Finds relevant screen captures, chat conversations, and documents
    across all imported sources. Results are ranked by relevance using
    hybrid search (semantic understanding + keyword matching).

    Examples:
    - "meetings about project alpha last week"
    - "code review feedback from yesterday"
    - "discussion about API design in Claude"
    """
    start_time = time.monotonic()

    try:
        # Validate and sanitize input
        sanitized_query = validate_search_query(query)

        # Call server search API
        client = await get_client()
        response = await client.post(
            "/api/search/",
            json={
                "query": sanitized_query,
                "limit": limit,
                "sources": sources,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Format results for LLM consumption
        results = data.get("results", [])
        if not results:
            result_text = "No matching memories found."
        else:
            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(
                    f"{i}. [{r['source']}] {r['timestamp'][:10]}\n"
                    f"   {r['text_preview']}"
                )
            result_text = f"Found {len(results)} relevant memories:\n\n" + "\n\n".join(formatted)

        # Audit log
        log_mcp_call(
            tool_name="search_memory",
            input_params={"query": sanitized_query, "limit": limit, "sources": sources},
            result_summary=f"{len(results)} results",
            duration_ms=(time.monotonic() - start_time) * 1000,
            success=True,
        )

        return result_text

    except httpx.HTTPStatusError as e:
        log_mcp_call(
            tool_name="search_memory",
            input_params={"query": query[:50], "limit": limit},
            result_summary="HTTP error",
            duration_ms=(time.monotonic() - start_time) * 1000,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        raise ToolError("Memory search temporarily unavailable")

    except Exception as e:
        logger.exception("search_memory_failed")
        log_mcp_call(
            tool_name="search_memory",
            input_params={"query": query[:50], "limit": limit},
            result_summary="Internal error",
            duration_ms=(time.monotonic() - start_time) * 1000,
            success=False,
            error=str(type(e).__name__),
        )
        raise ToolError("Search failed unexpectedly")
```

### catch_me_up Tool Implementation

```python
# tools/catchup.py
from typing import Annotated
from pydantic import Field
import time

from jarvis_mcp.server import mcp, logger
from jarvis_mcp.validators import validate_topic
from jarvis_mcp.audit import log_mcp_call
from mcp.exceptions import ToolError

@mcp.tool()
async def catch_me_up(
    topic: Annotated[str, Field(
        min_length=1,
        max_length=500,
        description="Project name, topic, or area to get caught up on"
    )],
    days: Annotated[int, Field(
        default=7,
        ge=1,
        le=30,
        description="How many days back to look"
    )] = 7,
) -> str:
    """Get a context summary for a topic or project.

    Reviews recent activity across all memory sources related to the
    specified topic, then provides a summary to help you get back
    up to speed quickly.

    Examples:
    - "project alpha" - summarize recent project activity
    - "API redesign" - catch up on API discussions
    - "team standup" - review recent standup notes
    """
    start_time = time.monotonic()

    try:
        sanitized_topic = validate_topic(topic)

        # Search for relevant content in time range
        from datetime import datetime, timedelta, timezone
        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(days=days)

        client = await get_client()
        response = await client.post(
            "/api/search/",
            json={
                "query": sanitized_topic,
                "limit": 20,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            result_text = f"No activity found for '{topic}' in the last {days} days."
        else:
            # Group by date and source for summary
            by_date: dict[str, list] = {}
            for r in results:
                date_key = r["timestamp"][:10]
                by_date.setdefault(date_key, []).append(r)

            sections = []
            for date, items in sorted(by_date.items(), reverse=True):
                section_items = [f"  - [{i['source']}] {i['text_preview'][:100]}"
                                for i in items[:3]]
                sections.append(f"**{date}**:\n" + "\n".join(section_items))

            result_text = (
                f"Context recovery for '{topic}' (last {days} days):\n\n"
                f"Found {len(results)} relevant items across {len(by_date)} days.\n\n"
                + "\n\n".join(sections[:5])
            )

        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": sanitized_topic, "days": days},
            result_summary=f"{len(results)} items across {len(by_date) if results else 0} days",
            duration_ms=(time.monotonic() - start_time) * 1000,
            success=True,
        )

        return result_text

    except Exception as e:
        logger.exception("catch_me_up_failed")
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic[:50], "days": days},
            result_summary="Failed",
            duration_ms=(time.monotonic() - start_time) * 1000,
            success=False,
            error=str(type(e).__name__),
        )
        raise ToolError("Context recovery failed")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom MCP implementations | Official MCP Python SDK | 2025 | Standardized, maintained, spec-compliant |
| Low-level Server class | FastMCP decorators | mcp 1.2+ | Cleaner code, automatic schema generation |
| HTTP transport | stdio for local servers | Ongoing | Simpler security, no auth needed for local |
| Manual logging | Structured JSON audit | Current | Machine-parseable, compliance-ready |
| Ad-hoc validation | OWASP MCP Top 10 guidance | Jan 2025 | Security best practices formalized |

**Deprecated/outdated:**
- **SSE transport for local servers**: deprecated in favor of HTTP; use stdio for local
- **Manual JSON-RPC handling**: use SDK which handles protocol correctly
- **v2-style FastMCP imports**: v2 is pre-alpha; stay on v1.x for production

## Open Questions

1. **Embedding model access from MCP server**
   - What we know: MCP server needs to call search API which uses embeddings
   - What's unclear: Should MCP server load embedding model directly or always call HTTP API?
   - Recommendation: Call HTTP API for clean separation; embedding model stays in server process

2. **Authentication between MCP and server**
   - What we know: Both run locally on same machine, server binds to 127.0.0.1
   - What's unclear: Do we need any auth token between MCP and server?
   - Recommendation: No auth needed for local-only; add shared secret if opening to network

3. **Error budget for MCP calls**
   - What we know: Claude Code has MCP timeout settings (MCP_TIMEOUT env var)
   - What's unclear: What's appropriate timeout for search operations?
   - Recommendation: Start with 30s default timeout; add client.post(timeout=25) to leave margin

## Sources

### Primary (HIGH confidence)
- [MCP Python SDK v1.26.0](https://pypi.org/project/mcp/) - Current stable version, Python 3.10+
- [FastMCP Tools Documentation](https://gofastmcp.com/servers/tools) - Decorator patterns, type handling
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp) - Configuration, stdio transport
- [MCP Build Server Tutorial](https://modelcontextprotocol.io/docs/develop/build-server) - Official quickstart

### Secondary (MEDIUM confidence)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices) - Input validation, audit requirements
- [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/) - MCP-specific vulnerabilities
- [structlog Documentation](https://www.structlog.org/en/stable/) - JSON logging patterns

### Tertiary (LOW confidence)
- Prompt injection patterns - community research, patterns may evolve
- v2 SDK timeline - "Q1 2026" mentioned but not official release

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official SDK with clear documentation, production-ready v1.x
- Architecture patterns: HIGH - Based on official examples and documentation
- Pitfalls: HIGH - Well-documented in official security guidance and OWASP
- Input validation: MEDIUM - Patterns derived from OWASP + Pydantic docs, may need tuning

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days - MCP SDK v1.x is stable)
