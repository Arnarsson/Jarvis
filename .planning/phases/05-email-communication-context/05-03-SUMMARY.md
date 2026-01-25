---
phase: 05
plan: 03
subsystem: email
tags: [embeddings, qdrant, search, arq]

dependency-graph:
  requires: [05-01, 05-02]
  provides: [email-search, email-embeddings]
  affects: [05-04]

tech-stack:
  added: []
  patterns: [embedding-reuse, source-filtering]

key-files:
  created:
    - server/src/jarvis_server/email/embeddings.py
  modified:
    - server/src/jarvis_server/processing/tasks.py
    - server/src/jarvis_server/processing/worker.py
    - server/src/jarvis_server/search/schemas.py
    - server/src/jarvis_server/api/search.py

decisions: []

metrics:
  duration: 2 min
  completed: 2026-01-25
---

# Phase 5 Plan 03: Email Search Integration (Embeddings) Summary

Email content embedded in Qdrant with dense+sparse vectors, searchable via existing hybrid search API with source="email" filter.

## Completed Tasks

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Create email embedding module | 1612bc2 | embed_email(), process_pending_emails() |
| 2 | Add email processing to ARQ tasks | ee208d2 | process_email_embeddings task registered |
| 3 | Update search API to support email source | 90786b2 | Schema descriptions updated |

## Implementation Details

### Email Embedding Module

Created `/server/src/jarvis_server/email/embeddings.py`:

- `embed_email(message)`: Generates embedding from subject + from + body (first 1000 chars)
- `process_pending_emails(db, batch_size)`: Batch processes pending emails
- Reuses `EmbeddingProcessor` for dense+sparse vector generation
- Stores in Qdrant with `source="email"` and email-specific metadata
- Includes `text_preview` formatted as "Email: {subject}\nFrom: {sender}"

### ARQ Task Integration

- Added `process_email_embeddings()` task function
- Registered in `WorkerSettings.functions` for background processing
- Processes pending emails in batches of 20
- Can be triggered via ARQ job queue after email sync

### Search API Updates

- Updated `SearchRequest.sources` description to include "email"
- Updated `SearchResult.source` description to include "email"
- Existing hybrid search automatically handles email results via Qdrant filtering

## Architecture Notes

The email embedding module follows the established pattern:

1. **Embedding Generation**: Uses `get_embedding_processor()` singleton (same as captures)
2. **Vector Storage**: Uses `get_qdrant().upsert_capture()` (same collection, different source)
3. **Search Integration**: Existing hybrid search works automatically with source filter

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- Email embedding module imports successfully
- ARQ task registered in worker functions list
- Search with `sources=["email"]` validates correctly
- EmbeddingProcessor reuse pattern verified

## Next Phase Readiness

Ready for 05-04 (email MCP tools):
- Emails can be synced (05-01, 05-02)
- Emails are searchable via hybrid search
- MCP tools can expose email search to Claude
