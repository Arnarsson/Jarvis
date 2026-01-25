# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Never lose context -- whether away 2 hours or 2 months, Jarvis catches you up on any project, decision, or thread.
**Current focus:** Phase 7: Web UI & Visualization

## Current Position

Phase: 7 of 7 (Web UI & Visualization)
Plan: 3 of 6 in current phase
Status: In progress
Last activity: 2026-01-25 -- Completed 07-03-PLAN.md

Progress: [################░░░░] 63% (40/63 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 40
- Average duration: 3 min
- Total execution time: 109 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 13 | 34 min | 2.6 min |
| 02 | 9 | 21 min | 2.3 min |
| 03 | 5 | 15 min | 3.0 min |
| 04 | 9 | 28 min | 3.1 min |
| 05 | 3 | 8 min | 2.7 min |
| 07 | 1 | 3 min | 3.0 min |

**Recent Trend:**
- Last 5 plans: 04-09 (2 min), 05-01 (4 min), 05-02 (2 min), 05-03 (2 min), 07-03 (3 min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Fork OpenRecall for desktop agent (Python-based, simpler ecosystem)
- [Init]: Qdrant for vector storage from start (avoid pgvector performance cliff)
- [Init]: Security/privacy foundational in Phase 1 (Microsoft Recall lesson)
- [01-01]: Hatchling build backend for agent package (modern, fast, PEP 517)
- [01-01]: src layout for proper package isolation
- [01-01]: lru_cache for singleton settings pattern
- [01-01]: Exclusions merge user config with bundled defaults
- [01-02]: Hatchling build backend for server package (modern, fast, good src layout)
- [01-02]: SQLAlchemy async_sessionmaker with expire_on_commit=False for API patterns
- [01-02]: pool_pre_ping=True for connection health verification
- [01-03]: dhash over phash for speed (sufficient for screenshot change detection)
- [01-03]: time.monotonic() for interval tracking (immune to clock changes)
- [01-03]: Primary monitor only in capture_active() - orchestrator will enhance
- [01-04]: UUID as string (36 chars) for cross-database portability
- [01-04]: Timestamp index for time-range query performance
- [01-04]: Date-partitioned storage ({YYYY}/{MM}/{DD}/{id}.jpg) for easy archival
- [01-04]: Async Alembic migrations with asyncio.run wrapper
- [01-05]: time.monotonic() for idle timestamps (immune to clock changes)
- [01-05]: NamedTuple for WindowInfo (immutable, hashable)
- [01-05]: Graceful error handling (return None vs raise)
- [01-06]: lru_cache for FileStorage singleton (single instance across requests)
- [01-06]: Dual health endpoints (/ for dashboards, /ready for load balancers)
- [01-06]: Structured logging with masked database URL for security
- [01-07]: httpx.AsyncClient for connection pooling
- [01-07]: No retry on 4xx errors (client errors not transient)
- [01-07]: SQLite for queue persistence (simple, no deps)
- [01-07]: 60-second minimum backoff between retries
- [01-07]: 5 max attempts before marking failed
- [01-09]: Protocol pattern for CaptureOrchestratorProtocol (decouples tray from orchestrator)
- [01-09]: Material Design RGB colors for cross-theme visibility
- [01-09]: Standalone mode support when no orchestrator connected
- [01-10]: PID file at ~/.local/share/jarvis/agent.pid for process management
- [01-10]: Pause signal via file touch (~/.local/share/jarvis/agent.paused)
- [01-10]: Config values set via environment variables (JARVIS_ prefix)
- [01-10]: Exclusions saved to user YAML file, merged with bundled defaults
- [01-08]: 1-second tick loop with ChangeDetector controlling captures
- [01-08]: Standard logging over structlog (avoid new dependency)
- [01-08]: Dated directory structure for captures (YYYY/MM/DD/HHMMSS_monitor.jpg)
- [01-08]: Callback pattern for capture/skip/state events
- [01-08]: Background upload worker with 5-second batch interval
- [01-11]: python-json-logger for agent (simpler, already in deps)
- [01-11]: structlog for server (richer context, request tracking)
- [01-11]: Lazy Presidio initialization to avoid 5-10s startup delay
- [01-11]: Custom regex patterns for API keys not covered by Presidio
- [01-12]: All ports bound to 127.0.0.1 only for Tailscale-exclusive access
- [01-12]: Multi-stage Docker build with non-root user for security
- [01-12]: Named volumes for persistent data (postgres, qdrant, captures)
- [02-01]: 384-dim dense vectors for bge-small-en-v1.5 embedding model
- [02-01]: Sparse vectors in-memory (on_disk=False) for performance
- [02-01]: QdrantWrapper singleton via get_qdrant() with lru_cache
- [02-06]: orjson for fast JSON parsing of large exports
- [02-06]: Iterator[Conversation] pattern for memory-efficient parsing
- [02-06]: Flexible field name handling for export format variations
- [02-02]: BAAI/bge-small-en-v1.5 for dense embeddings (384-dim, fast, good quality)
- [02-02]: SPLADE for sparse embeddings (learned sparse, better than TF-IDF)
- [02-02]: Lazy model loading (avoid 5-10s startup delay on import)
- [02-02]: lru_cache singleton pattern for processors
- [02-08]: ISO timestamp cursor for pagination (efficient, deterministic ordering)
- [02-08]: SQL date() function for grouping captures by day (database-level aggregation)
- [02-03]: max_jobs=5 to limit concurrent OCR jobs (memory intensive)
- [02-03]: job_timeout=300s (5 min) per capture for OCR+embedding
- [02-03]: Cron every 6 hours for backlog processing
- [02-03]: AsyncSessionLocal for DB access in ARQ tasks (direct factory access)
- [02-04]: Prefetch 5x limit from each vector type for quality RRF fusion
- [02-04]: Filters at Qdrant level (not post-filtering) for efficiency
- [02-04]: Graceful fallback for missing/malformed payload timestamps
- [02-07]: Inline embedding during import for immediate searchability
- [02-07]: Temp file with cleanup for upload handling
- [02-07]: Skip duplicates silently (external_id + source uniqueness)
- [02-05]: ARQ pool in app.state for endpoint access to job queue
- [02-05]: Non-blocking enqueue (graceful failure if Redis unavailable)
- [02-05]: Backlog cron catches any missed captures
- [02-09]: Model cache to /tmp (avoids volume permission issues, re-downloads on restart)
- [02-09]: OpenCV system libs added to Dockerfile for EasyOCR support
- [03-01]: mcp[cli]>=1.26.0,<2 pinned for v1.x stability
- [03-01]: structlog configured to stderr before any other imports (stdio transport)
- [03-01]: httpx.AsyncClient with 25s timeout (margin for MCP 30s timeout)
- [03-01]: Lazy singleton pattern for HTTP client initialization
- [03-02]: Regex patterns for prompt injection detection (code blocks, headers, delimiters, instruction markers)
- [03-02]: 200 char truncation for params, 500 for errors to prevent log bloat
- [03-02]: Log suspicious inputs BEFORE rejection for security monitoring
- [03-03]: ToolError from mcp.server.fastmcp.exceptions for clean error handling
- [03-03]: Date-only formatting (YYYY-MM-DD) from ISO timestamps for readability
- [03-03]: Numbered list format for results (LLM-friendly output)
- [03-04]: 20 result limit for context recovery (more than search_memory's default 10)
- [03-04]: Max 5 dates with 3 items per date to avoid overwhelming output
- [03-04]: Days parameter capped at 30 to prevent excessive queries
- [04-01]: Refactored Base class to db/base.py to avoid circular imports
- [04-01]: Read-only calendar scope (calendar.readonly) for v1 security
- [04-01]: Token storage at JARVIS_DATA_DIR/calendar/token.json for persistence
- [04-01]: CalendarAuthRequired exception pattern for auth-gated endpoints
- [04-02]: Full sync fetches last 30 days + unlimited future events
- [04-02]: Sync token stored in SyncState model for persistence
- [04-02]: 410 HttpError triggers automatic token deletion and full resync
- [04-02]: Both foreground (immediate) and background (ARQ) sync modes available
- [04-03]: Regex patterns for Zoom, Google Meet, Teams detection
- [04-03]: 2-second check interval for meeting detection worker
- [04-03]: 15-minute window for meeting-to-calendar correlation
- [04-04]: claude-sonnet-4-20250514 model for brief generation (fast, cost-effective)
- [04-04]: Hybrid search for memory context (semantic + keyword)
- [04-04]: Brief caching in Meeting.brief field
- [04-04]: Lazy Anthropic client initialization
- [04-05]: ConsentToken pattern for explicit recording consent
- [04-05]: 16kHz mono audio for speech recognition optimization
- [04-05]: Lazy directory creation to avoid permission errors at import
- [04-05]: Consent verification at upload endpoint
- [04-06]: faster-whisper over standard whisper (GPU-optimized CTranslate2 backend)
- [04-06]: VAD filter enabled by default (skip silence, faster processing)
- [04-06]: Model size configurable via WHISPER_MODEL_SIZE env var (default: base)
- [04-06]: GPU auto-detection with CPU fallback for portability
- [04-07]: claude-sonnet-4-20250514 model for summarization (consistent with briefs)
- [04-07]: Auto-queue summarization after transcription via ARQ redis context
- [04-07]: Truncate transcripts >100k chars to stay within token limits
- [04-07]: Store action items as JSON string in Meeting.action_items_json
- [04-08]: Follow existing search.py patterns for consistent MCP tool implementation
- [04-08]: Separate calendar and meeting tools into distinct modules for clarity
- [04-08]: Use httpx.HTTPStatusError for specific HTTP error handling
- [04-09]: OAuth helper script for Docker environments (can't open browser in container)
- [04-09]: google_event_id increased to 255 chars for recurring event IDs
- [04-09]: Handle 400 errors only when sync_token present (avoid infinite retry loop)
- [05-01]: Port 8091 for Gmail OAuth callback (calendar uses 8090)
- [05-01]: gmail.readonly scope for v1 security
- [05-01]: Separate email models from db/models.py (no circular import)
- [05-01]: Email models imported in alembic/env.py for autogenerate
- [05-02]: Gmail History API for incremental sync (efficient, only changed messages)
- [05-02]: BeautifulSoup for HTML body extraction (fallback when text/plain unavailable)
- [05-02]: Initial sync fetches last 30 days (balance completeness/performance)
- [05-03]: Reuse EmbeddingProcessor for email embeddings (consistency with captures)
- [05-03]: Store emails in same Qdrant collection with source="email" filter
- [05-03]: text_preview formatted as "Email: {subject}\nFrom: {sender}"
- [07-01]: TailwindCSS via CDN (no build step needed)
- [07-01]: HTMX for partial page updates (server-rendered HTML)
- [07-01]: Alpine.js for client-side state (lightweight, HTMX-friendly)
- [07-01]: Jinja2 template inheritance pattern
- [07-02]: Date picker dropdown with capture counts per day
- [07-02]: Infinite scroll via IntersectionObserver and HTMX revealed trigger
- [07-02]: Modal with prev/next navigation for chronological browsing
- [07-02]: OCR text panel with copy-to-clipboard functionality
- [07-03]: highlight_query Jinja2 filter with regex and markupsafe (XSS-safe)
- [07-03]: Source badge colors: screen (blue), chatgpt (green), claude (orange), grok (purple), email (red)
- [07-03]: 300ms debounce delay for HTMX search trigger

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-01-25T15:41:15Z
Stopped at: Completed 07-03-PLAN.md
Resume file: None
Next: 07-04-PLAN.md (Calendar view)
