# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Never lose context -- whether away 2 hours or 2 months, Jarvis catches you up on any project, decision, or thread.
**Current focus:** Phase 1: Privacy-First Capture Foundation

## Current Position

Phase: 1 of 7 (Privacy-First Capture Foundation)
Plan: 12 of 13 in current phase
Status: In progress
Last activity: 2026-01-24 -- Completed 01-12-PLAN.md (Docker Infrastructure)

Progress: [#########.] ~92%

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 3 min
- Total execution time: 34 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 12 | 34 min | 2.8 min |

**Recent Trend:**
- Last 5 plans: 01-09 (2 min), 01-10 (4 min), 01-08 (4 min), 01-11 (6 min), 01-12 (2 min)
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

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-01-24T21:02:12Z
Stopped at: Completed 01-12-PLAN.md (Docker Infrastructure)
Resume file: None
