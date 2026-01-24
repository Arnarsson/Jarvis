---
phase: 02
plan: 08
subsystem: api
tags: [timeline, api, pagination, fastapi]
dependency-graph:
  requires: [02-01]
  provides: [timeline-api, day-summaries-api, capture-detail-api]
  affects: [frontend-timeline-view]
tech-stack:
  added: []
  patterns: [cursor-based-pagination, date-grouping, async-sqlalchemy]
key-files:
  created:
    - server/src/jarvis_server/api/timeline.py
  modified:
    - server/src/jarvis_server/api/__init__.py
    - server/src/jarvis_server/main.py
decisions:
  - id: cursor-pagination
    choice: ISO timestamp cursor for pagination (efficient, deterministic ordering)
  - id: day-grouping
    choice: SQL date() function for grouping captures by day (database-level aggregation)
metrics:
  duration: 1 min
  completed: 2026-01-24
---

# Phase 2 Plan 8: Timeline API Summary

**One-liner:** Timeline browsing API with cursor-based pagination, day summaries, and capture detail endpoint

## Completed Tasks

| Task | Name | Files | Commit |
|------|------|-------|--------|
| 1 | Create timeline API schemas and endpoint | timeline.py | pending |
| 2 | Register timeline router in app | __init__.py, main.py | pending |

## Key Implementation Details

### Timeline API Endpoints

1. **GET /api/timeline/** - Main timeline endpoint
   - Returns captures in reverse chronological order (newest first)
   - Cursor-based pagination using ISO timestamp
   - Limit parameter (1-200, default 50)
   - Date range filtering (start_date, end_date)
   - Returns total count, has_more flag, and next_cursor

2. **GET /api/timeline/days** - Day summaries for calendar view
   - Groups captures by date
   - Returns count, first/last capture timestamps per day
   - Useful for date pickers and calendar visualization
   - Limit parameter (1-365, default 30)

3. **GET /api/timeline/{capture_id}** - Capture detail
   - Returns full capture information including OCR text
   - 404 if capture not found

### Design Choices

- **Cursor-based pagination:** More efficient than offset-based for large datasets, maintains consistency during insertions
- **ISO timestamp cursor:** Human-readable, sortable, no extra index needed
- **Day grouping in SQL:** Pushes aggregation to database for efficiency
- **Text preview:** Truncates OCR text to 200 chars for timeline display

## Verification Results

All checks passed:
- Router import: OK
- Main.py includes timeline_router: OK
- Import from api module: OK

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Timeline API is ready for:
- Frontend timeline view integration
- Date picker/calendar component
- Infinite scroll implementation using cursor pagination
