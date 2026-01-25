---
phase: 05-email-communication-context
plan: 02
subsystem: email
tags: [gmail, sync, history-api, incremental-sync]
depends_on:
  requires: [05-01]
  provides: [email-sync-service, email-sync-endpoint]
  affects: [05-03, 05-04, 05-05]
tech_stack:
  added: [beautifulsoup4]
  patterns: [gmail-history-api, incremental-sync]
key_files:
  created:
    - server/src/jarvis_server/email/sync.py
  modified:
    - server/src/jarvis_server/api/email.py
    - server/pyproject.toml
decisions:
  - id: history-api-sync
    choice: "Gmail History API for incremental sync"
    reason: "Efficient - only fetches changed messages instead of full re-sync"
  - id: html-fallback
    choice: "BeautifulSoup for HTML body extraction"
    reason: "Email bodies may only be HTML; need text extraction for search/embedding"
  - id: initial-sync-30d
    choice: "Initial sync fetches last 30 days"
    reason: "Balance between completeness and performance"
metrics:
  duration: 3 min
  completed: 2026-01-25
---

# Phase 5 Plan 02: Email Incremental Sync Service Summary

Gmail sync service using History API for efficient incremental sync with text/plain preference and HTML fallback for body extraction.

## What Was Built

### Email Sync Service (`server/src/jarvis_server/email/sync.py`)

Core sync module implementing Gmail message synchronization:

**Key Functions:**
- `sync_emails(db, full_sync=False)` - Main entry point, returns `{created, updated, deleted}`
- `initial_sync(service, db, days_back=30)` - Full sync of recent messages
- `incremental_sync(service, db, start_history_id)` - Uses Gmail History API for efficiency
- `parse_email_headers(headers)` - Extracts Subject, From (name + address), To, Cc, Date
- `extract_body_text(payload)` - Handles multipart, prefers text/plain, HTML fallback
- `store_message(db, message)` - Upserts message with full metadata and labels

**Sync State Management:**
- `get_history_id()` / `save_history_id()` / `delete_history_id()` - Persist history ID
- Automatic full resync on 404/410 (history expired)

### API Endpoints

Added to `server/src/jarvis_server/api/email.py`:

```
POST /api/email/sync
  Query: full_sync (bool, default False)
  Returns: {status, created, updated, deleted}

GET /api/email/sync/status
  Returns: {last_sync, history_id, message_count}
```

### Dependencies

- Added `beautifulsoup4>=4.12.0` for HTML tag stripping

## Technical Details

### Gmail History API Pattern

```python
# Initial sync - query recent messages
messages_result = service.users().messages().list(
    userId="me", q=f"newer_than:{days_back}d", maxResults=500
).execute()

# Incremental sync - get only changes
history_result = service.users().history().list(
    userId="me",
    startHistoryId=start_history_id,
    historyTypes=["messageAdded", "messageDeleted"],
).execute()
```

### Body Text Extraction

1. Search message payload for `text/plain` part
2. If not found, search for `text/html` part
3. Strip HTML using BeautifulSoup (removes script/style, preserves text)
4. Base64 URL-safe decode all content

### Header Parsing

Uses `email.utils.parseaddr` for From/To/Cc address extraction and `parsedate_to_datetime` for date parsing.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| d202366 | feat | Create email sync service with Gmail History API |
| 770447f | feat | Add sync endpoints to email API |
| bf868a1 | chore | Add beautifulsoup4 dependency |

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Ready for 05-03 (Email indexing and ARQ worker):
- [x] Sync service fetches and stores messages
- [x] Messages include body_text for embedding
- [x] processing_status field ready for worker to use
- [x] Sync endpoint available for manual/scheduled triggers
