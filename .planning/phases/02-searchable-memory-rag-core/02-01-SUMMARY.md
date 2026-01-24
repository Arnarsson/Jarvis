---
phase: 02-searchable-memory-rag-core
plan: 01
subsystem: infra
tags: [redis, qdrant, vector-search, hybrid-vectors, arq]

# Dependency graph
requires:
  - phase: 01-privacy-first-capture-foundation
    provides: Docker Compose base with Qdrant, server config patterns
provides:
  - Redis service for ARQ background task queue
  - QdrantWrapper with hybrid vector collection (dense + sparse)
  - upsert_capture() method for embedding storage
  - Timestamp and source payload indices for filtering
affects: [02-02 (embedding pipeline), 02-03 (search API)]

# Tech tracking
tech-stack:
  added: [redis:7-alpine, qdrant-client models]
  patterns: [hybrid vector configuration, singleton wrapper with lru_cache]

key-files:
  created:
    - server/src/jarvis_server/vector/__init__.py
    - server/src/jarvis_server/vector/qdrant.py
  modified:
    - server/docker-compose.yml
    - server/src/jarvis_server/config.py

key-decisions:
  - "384-dim dense vectors for bge-small-en-v1.5 embedding model"
  - "Sparse vectors in-memory (on_disk=False) for performance"
  - "DATETIME index on timestamp for time-range filtering"
  - "KEYWORD index on source for metadata filtering"

patterns-established:
  - "QdrantWrapper singleton via get_qdrant() with lru_cache"
  - "Hybrid vector config with named vectors (dense/sparse)"

# Metrics
duration: 1min
completed: 2026-01-24
---

# Phase 2 Plan 1: RAG Infrastructure Summary

**Redis for ARQ task queue and Qdrant hybrid collection with 384-dim dense + sparse vectors and payload indices**

## Performance

- **Duration:** 1 min 27 sec
- **Started:** 2026-01-24T22:06:10Z
- **Completed:** 2026-01-24T22:07:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Redis service added to Docker Compose with healthcheck and localhost-only binding
- QdrantWrapper class with hybrid vector collection setup
- upsert_capture() method for storing capture embeddings with dense + sparse vectors
- Config extended with redis_host and redis_port settings

## Task Commits

This plan will be committed as a single atomic commit covering both tasks.

## Files Created/Modified
- `server/docker-compose.yml` - Added Redis service, redis_data volume, JARVIS_REDIS_* env vars
- `server/src/jarvis_server/vector/__init__.py` - Module init with exports
- `server/src/jarvis_server/vector/qdrant.py` - QdrantWrapper with hybrid collection setup and upsert_capture
- `server/src/jarvis_server/config.py` - Added redis_host and redis_port settings

## Decisions Made
- 384-dim dense vectors for bge-small-en-v1.5 (matching planned embedding model)
- Sparse vectors in-memory for performance (on_disk=False)
- DATETIME payload index on timestamp for time-range queries
- KEYWORD payload index on source for metadata filtering
- Collection named "captures" to match Phase 1 capture model

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Redis ready for ARQ worker integration (Plan 02-02)
- Qdrant collection ready for embedding pipeline (Plan 02-02)
- upsert_capture() ready for OCR text embedding storage

---
*Phase: 02-searchable-memory-rag-core*
*Completed: 2026-01-24*
