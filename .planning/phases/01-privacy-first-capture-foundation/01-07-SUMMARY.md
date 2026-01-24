---
phase: 01-privacy-first-capture-foundation
plan: 07
subsystem: agent-sync
tags: [python, httpx, sqlite, upload, queue, retry]

# Dependency graph
requires: [01-03]
provides:
  - Async HTTP uploader with exponential backoff retry
  - SQLite-backed persistent queue for offline captures
  - Connection pooling via httpx.AsyncClient
affects: [01-06, capture-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns: [exponential-backoff, persistent-queue, async-context-manager]

key-files:
  created:
    - agent/src/jarvis/sync/__init__.py
    - agent/src/jarvis/sync/uploader.py
    - agent/src/jarvis/sync/queue.py
  modified: []

key-decisions:
  - "httpx.AsyncClient for connection pooling and async HTTP"
  - "No retry on 4xx errors (client errors are not transient)"
  - "SQLite for queue persistence (simple, no external deps)"
  - "60-second backoff minimum between retry attempts"
  - "5 max attempts before marking failed"
  - "UUID for queue item IDs"

patterns-established:
  - "Upload retry: exponential backoff (2^attempt seconds)"
  - "Queue state machine: pending -> uploading -> completed/failed"
  - "Async context manager for resource cleanup"

# Metrics
duration: 3min
completed: 2026-01-24
---

# Phase 01 Plan 07: Agent-to-Server Upload with Retry Queue Summary

**Async HTTP uploader with exponential backoff retry and SQLite-backed persistent queue for offline captures**

## Performance

- **Duration:** 2m 43s
- **Started:** 2026-01-24T20:44:32Z
- **Completed:** 2026-01-24T20:47:15Z
- **Tasks:** 2/2
- **Files created:** 3

## Accomplishments

- CaptureUploader class uses httpx.AsyncClient for efficient connection pooling
- Exponential backoff retry: 2, 4, 8... seconds between attempts
- No retry on 4xx client errors (only transient 5xx/connection errors)
- UploadResult dataclass provides structured upload feedback
- upload() for files, upload_bytes() for in-memory data
- check_server() verifies server availability
- Async context manager support for proper resource cleanup
- UploadQueue persists captures in SQLite for durability
- Queue tracks attempts, last_attempt, and status per item
- 60-second minimum backoff between retry attempts
- Items marked 'failed' after 5 unsuccessful attempts
- cleanup_old() removes stale failed items

## Task Commits

Each task was committed atomically:

1. **Task 1: Async HTTP uploader with retry** - `da0170c` (feat)
2. **Task 2: Persistent upload queue** - `14c0da5` (feat)

## Files Created/Modified

- `agent/src/jarvis/sync/__init__.py` - Module exports (CaptureUploader, UploadQueue, etc.)
- `agent/src/jarvis/sync/uploader.py` - CaptureUploader class with httpx and retry logic
- `agent/src/jarvis/sync/queue.py` - UploadQueue class with SQLite persistence

## Decisions Made

- **httpx.AsyncClient for uploads:** Provides connection pooling, async/await support, and modern HTTP/2 capability
- **No retry on 4xx:** Client errors (bad request, auth failures) are not transient and shouldn't be retried
- **SQLite for queue:** Simple, no external dependencies, sufficient for single-agent queue operations
- **60-second minimum backoff:** Prevents hammering the server while allowing timely recovery
- **5 max attempts:** Balances reliability with avoiding infinite retry loops
- **UUID for queue IDs:** Globally unique, no coordination needed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - httpx was already in dependencies, all imports resolved correctly.

## User Setup Required

None - no external service configuration required.

## Verification Results

| Check | Result |
|-------|--------|
| CaptureUploader exponential backoff | PASS (2s for 2 retries) |
| Queue persistence across restart | PASS |
| Failed uploads queued for retry | PASS |
| Queue tracks attempt counts | PASS |
| Items marked failed after max attempts | PASS |

## Next Phase Readiness

- Sync module ready for capture orchestrator integration
- CaptureUploader handles all upload scenarios (file/bytes, retry, failure)
- UploadQueue provides reliable offline storage
- Can be imported: `from jarvis.sync import CaptureUploader, UploadQueue`
- Next: 01-06 will integrate these into the capture orchestrator

---
*Phase: 01-privacy-first-capture-foundation*
*Completed: 2026-01-24*
