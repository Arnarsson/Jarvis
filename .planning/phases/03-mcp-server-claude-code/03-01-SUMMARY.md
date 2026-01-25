---
phase: 03-mcp-server-claude-code
plan: 01
subsystem: mcp
tags: [mcp, fastmcp, httpx, structlog, stdio]

# Dependency graph
requires:
  - phase: 02-searchable-memory-rag-core
    provides: Search API endpoints for memory queries
provides:
  - Installable jarvis-mcp Python package
  - FastMCP server skeleton with stdio transport
  - Async HTTP client for server API calls
  - Structured logging to stderr (stdio-safe)
affects: [03-02, 03-03, 03-04, 03-05]

# Tech tracking
tech-stack:
  added: [mcp>=1.26.0, httpx>=0.27, structlog>=24.0, pydantic>=2.0]
  patterns: [stderr-only logging for stdio transport, lazy singleton HTTP client]

key-files:
  created:
    - mcp/pyproject.toml
    - mcp/src/jarvis_mcp/__init__.py
    - mcp/src/jarvis_mcp/server.py
    - mcp/src/jarvis_mcp/client.py
    - mcp/README.md
  modified: []

key-decisions:
  - "mcp[cli]>=1.26.0,<2 pinned for v1.x stability"
  - "structlog configured to stderr before any other imports"
  - "httpx.AsyncClient with 25s timeout (margin for MCP 30s timeout)"
  - "Lazy singleton pattern for HTTP client initialization"

patterns-established:
  - "stderr-only logging: structlog configured at module top, PrintLoggerFactory(file=sys.stderr)"
  - "Lazy HTTP client: global _client with get_client() async function"

# Metrics
duration: 3min
completed: 2026-01-25
---

# Phase 03 Plan 01: MCP Package Foundation Summary

**FastMCP server skeleton with stdio transport and async HTTP client for Jarvis memory tools**

## Performance

- **Duration:** 3 min (163 seconds)
- **Started:** 2026-01-25T11:23:56Z
- **Completed:** 2026-01-25T11:27:00Z
- **Tasks:** 3
- **Files created:** 5

## Accomplishments
- Created installable jarvis-mcp Python package with hatchling build backend
- Implemented async HTTP client with connection pooling for server API calls
- Built FastMCP server skeleton that runs with stdio transport without stdout pollution
- Configured structured logging to stderr only (critical for JSON-RPC protocol)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create MCP package with pyproject.toml** - `9a4d600` (feat)
2. **Task 2: Create HTTP client for server API** - `fdb3cdf` (feat)
3. **Task 3: Create FastMCP server skeleton** - `dd8a6e7` (feat)

## Files Created

- `mcp/pyproject.toml` - Package configuration with mcp[cli], httpx, structlog dependencies
- `mcp/src/jarvis_mcp/__init__.py` - Package init with version 0.1.0
- `mcp/src/jarvis_mcp/server.py` - FastMCP server with stdio transport, stderr logging
- `mcp/src/jarvis_mcp/client.py` - Async HTTP client for server API with lazy singleton
- `mcp/README.md` - Basic package documentation (required for hatchling build)

## Decisions Made

- **mcp[cli]>=1.26.0,<2**: Pin to v1.x for stability, includes CLI extras
- **Python >=3.10**: Wider compatibility than server (which requires 3.11)
- **stderr-only logging**: Critical for stdio transport - stdout breaks JSON-RPC protocol
- **25s HTTP timeout**: Leave margin for MCP's 30s timeout on tool calls
- **Lazy client initialization**: Create httpx.AsyncClient on first use, not import

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added README.md for hatchling build**
- **Found during:** Task 1 (Package creation)
- **Issue:** pyproject.toml referenced README.md which didn't exist, causing build failure
- **Fix:** Created README.md with basic package documentation
- **Files created:** mcp/README.md
- **Verification:** Package builds and installs successfully
- **Committed in:** 9a4d600 (Task 1 commit)

**2. [Rule 1 - Bug] Removed mask_error_details parameter**
- **Found during:** Task 3 (Server creation)
- **Issue:** FastMCP.__init__() doesn't have mask_error_details parameter in mcp 1.26.0
- **Fix:** Removed the parameter, using default FastMCP configuration
- **Files modified:** mcp/src/jarvis_mcp/server.py
- **Verification:** Server starts without error
- **Committed in:** dd8a6e7 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for functionality. No scope creep.

## Issues Encountered

None - all issues were handled via deviation rules.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MCP package installable and running
- Server starts with stdio transport
- HTTP client ready for API calls
- Ready for Plan 02: Input validation and audit logging

---
*Phase: 03-mcp-server-claude-code*
*Completed: 2026-01-25*
