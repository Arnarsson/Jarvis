---
phase: 02-searchable-memory-rag-core
plan: 03
subsystem: processing
tags: [arq, redis, background-processing, ocr, embeddings, qdrant]

# Dependency graph
requires:
  - phase: 02-01
    provides: Qdrant wrapper and collection setup
  - phase: 02-02
    provides: OCR and embedding processors
provides:
  - ARQ background processing pipeline for captures
  - process_capture task for single capture processing
  - process_backlog task for batch processing
  - WorkerSettings configuration for ARQ worker
  - processing_status field on Capture model
affects: [02-04, api-endpoints, worker-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ARQ task pattern with ctx dict for shared resources
    - Lazy worker initialization in on_startup
    - Cron-based backlog processing

key-files:
  created:
    - server/src/jarvis_server/processing/pipeline.py
    - server/src/jarvis_server/processing/tasks.py
    - server/src/jarvis_server/processing/worker.py
    - server/alembic/versions/002_add_processing_status.py
  modified:
    - server/src/jarvis_server/db/models.py
    - server/src/jarvis_server/processing/__init__.py
    - server/pyproject.toml

key-decisions:
  - "max_jobs=5 to limit concurrent OCR jobs (memory intensive)"
  - "job_timeout=300s (5 min) per capture for OCR+embedding"
  - "Cron every 6 hours for backlog processing"
  - "AsyncSessionLocal for DB access in tasks (not dependency injection)"

patterns-established:
  - "ARQ task ctx pattern: shared processors initialized in on_startup"
  - "Pipeline orchestration: load -> OCR -> embed -> Qdrant upsert -> status update"

# Metrics
duration: 2min
completed: 2026-01-24
---

# Phase 2 Plan 3: Processing Pipeline Summary

**ARQ background processing pipeline with OCR -> embedding -> Qdrant upsert orchestration, max_jobs=5 concurrency, and 6-hour cron backlog processing**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-24T22:11:42Z
- **Completed:** 2026-01-24T22:13:48Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Added processing_status field to Capture model with database index for efficient backlog queries
- Created pipeline.py with process_single_capture orchestrating: load capture -> OCR -> store text -> embed -> Qdrant upsert -> mark complete
- Created ARQ tasks for single capture processing and backlog batch processing
- Created WorkerSettings with max_jobs=5, 5-min timeout, cron every 6 hours, and lazy processor initialization

## Task Commits

All tasks committed together (atomic implementation):

1. **Task 1: Add processing_status to Capture model** - `6804a0f`
2. **Task 2: Create processing pipeline and ARQ tasks** - `6804a0f`
3. **Task 3: Create ARQ worker configuration** - `6804a0f`

## Files Created/Modified
- `server/src/jarvis_server/db/models.py` - Added processing_status field with index
- `server/alembic/versions/002_add_processing_status.py` - Migration for new column
- `server/src/jarvis_server/processing/pipeline.py` - Pipeline orchestration (process_single_capture, get_pending_captures)
- `server/src/jarvis_server/processing/tasks.py` - ARQ task definitions (process_capture, process_backlog)
- `server/src/jarvis_server/processing/worker.py` - WorkerSettings class for ARQ configuration
- `server/src/jarvis_server/processing/__init__.py` - Updated exports
- `server/pyproject.toml` - Added jarvis-worker entry point

## Decisions Made
- max_jobs=5: Limit concurrent OCR jobs since they are memory intensive
- job_timeout=300s: 5 minutes per capture allows for complex OCR scenarios
- Cron every 6 hours: Balance between catching backlogs and not overwhelming system
- AsyncSessionLocal usage: Direct session factory access in tasks rather than dependency injection (worker context differs from FastAPI)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Processing pipeline ready for integration with capture upload endpoint
- Worker can be started with: `arq jarvis_server.processing.worker.WorkerSettings`
- Ready for 02-04 (search endpoint) which will query processed captures in Qdrant

---
*Phase: 02-searchable-memory-rag-core*
*Completed: 2026-01-24*
