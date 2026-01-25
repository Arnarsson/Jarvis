---
phase: 07-web-ui-visualization
plan: 05
subsystem: web-ui
tags: [settings, htmx, status, integrations, tailwind]
depends_on:
  requires: [07-01]
  provides: [settings-ui, status-api, sync-triggers]
  affects: [07-06]
tech-stack:
  added: []
  patterns: [htmx-partials, service-health-checks]
key-files:
  created:
    - server/src/jarvis_server/web/templates/partials/status-cards.html
    - server/src/jarvis_server/web/templates/partials/integration-settings.html
  modified:
    - server/src/jarvis_server/web/templates/settings.html
    - server/src/jarvis_server/web/api.py
    - server/src/jarvis_server/web/routes.py
decisions:
  - id: service-health-endpoints
    choice: Check Redis via redis-py ping, Qdrant via get_collection
    reason: Direct service checks provide accurate health status
  - id: storage-calculation
    choice: Recursive directory size with 100GB assumed max
    reason: Simple progress bar without filesystem queries for total space
  - id: integration-status-display
    choice: Show credentials_exist vs authenticated states
    reason: Guide users through setup process (credentials first, then OAuth)
metrics:
  duration: 4 min
  completed: 2026-01-25
---

# Phase 7 Plan 05: Settings and Configuration UI Summary

Settings page with HTMX-powered status monitoring and integration management.

## What Was Built

### Settings Page (settings.html)
- System status section with HTMX-loaded status cards
- Refresh button to manually reload service health
- Integrations section loaded dynamically via HTMX
- Capture configuration display (storage path, data dir, database, log level)
- Privacy settings section (read-only, shows enabled features)

### Status Cards Partial (status-cards.html)
- Server status with version display
- PostgreSQL status with capture count
- Redis status (task queue health)
- Qdrant status with vector count
- Storage usage bar with percentage and file count
- Last checked timestamp

### Integration Settings Partial (integration-settings.html)
- Google Calendar integration:
  - Auth status badge (connected/not connected)
  - Sync Now button when authenticated
  - Connect button when credentials exist but not authenticated
  - Setup required indicator when credentials missing
  - Events count and last sync time
- Gmail integration:
  - Same pattern as Calendar
  - Emails count and last sync time
- AI Conversations section:
  - Manual import indicator
  - Conversation count

### Settings API Endpoints
- `GET /api/web/settings/status` - Service health checks
- `GET /api/web/settings/integrations` - Integration status
- `POST /api/web/settings/calendar/sync` - Trigger calendar sync
- `POST /api/web/settings/gmail/sync` - Trigger Gmail sync

## Key Implementation Details

### Service Health Checks
```python
# PostgreSQL - via SQLAlchemy session
await session.execute(text("SELECT 1"))

# Redis - via redis-py ping
r = redis.Redis(host=settings.redis_host, port=settings.redis_port)
r.ping()

# Qdrant - via collection info
client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
collection_info = client.get_collection("captures")
```

### Integration Auth Checks
Reuses existing OAuth modules:
- `calendar.oauth.is_authenticated()` - Checks for valid/refreshable token
- `calendar.oauth.credentials_exist()` - Checks for credentials.json
- Same pattern for email.oauth

### Sync Triggers
Both sync endpoints:
1. Call the sync function directly
2. Catch auth exceptions gracefully
3. Return updated integrations partial with success/error toast

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Service health endpoints | Direct Redis ping, Qdrant get_collection | More accurate than assuming service is up |
| Storage calculation | Recursive rglob with 100GB assumed max | Simple approach without requiring filesystem info |
| Integration status | Three states: authenticated, credentials_exist, neither | Guides users through two-step setup |

## Verification

All verification criteria met:
- [x] Navigate to /settings - Page renders with all sections
- [x] System status shows for all services - 4 status cards displayed
- [x] Google Calendar integration status visible - Auth status and stats shown
- [x] Trigger calendar sync works - POST endpoint functional

## File Changes

### Created
- `server/src/jarvis_server/web/templates/partials/status-cards.html` (150 lines)
- `server/src/jarvis_server/web/templates/partials/integration-settings.html` (157 lines)

### Modified
- `server/src/jarvis_server/web/templates/settings.html` - Full rewrite with HTMX
- `server/src/jarvis_server/web/api.py` - Added 4 settings endpoints
- `server/src/jarvis_server/web/routes.py` - Added config context to settings route

## Commits

1. `b1df79d` - feat(07-05): update settings page with system status and integrations
2. `bbe094d` - feat(07-05): add status cards partial for service health display
3. `fc4a9a9` - feat(07-05): add integration settings partial for OAuth status
4. `2b8c7f5` - feat(07-05): add settings API endpoints for status and sync

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Ready for 07-06 (final polish/documentation):
- All pages complete (Dashboard, Timeline, Search, Calendar, Settings)
- All HTMX partials implemented
- All API endpoints functional
- Consistent UI patterns across all pages
