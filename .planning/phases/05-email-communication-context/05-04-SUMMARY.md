---
phase: 05
plan: 04
subsystem: meetings
tags: [email-context, briefs, search, llm]

dependency-graph:
  requires: [05-01, 05-02, 05-03]
  provides: [email-enriched-briefs]
  affects: []

tech-stack:
  added: []
  patterns: [async-context-gathering, dual-context-search]

key-files:
  created:
    - server/src/jarvis_server/email/search.py
  modified:
    - server/src/jarvis_server/meetings/briefs.py

decisions:
  - Semantic search via hybrid_search with source="email" filter
  - Limit to 10 attendee emails per meeting to avoid huge queries
  - 30-day lookback for both attendee and topic searches

metrics:
  duration: 2 min
  completed: 2026-01-25
---

# Phase 5 Plan 04: Pre-meeting Brief Enrichment with Email Context Summary

Pre-meeting briefs now include relevant email threads from/to meeting attendees and about meeting topics, providing richer context for preparation.

## Completed Tasks

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Create email search for meeting context | 832bd1b | search_emails_for_meeting(), format_email_context() |
| 2 | Update brief generation to include email context | 9c4c4f4 | BRIEF_PROMPT, gather_meeting_context() |

## Implementation Details

### Email Search Module

Created `/server/src/jarvis_server/email/search.py`:

- `search_emails_for_meeting(db, attendee_emails, meeting_topic, lookback_days, max_results)`:
  - Searches by attendee addresses (from/to fields using ilike)
  - Semantic search by meeting topic via hybrid_search with source="email"
  - Deduplicates results and sorts by date descending
  - Returns list of EmailMessage objects

- `format_email_context(emails)`:
  - Formats emails for inclusion in brief prompt
  - Includes date, sender name, subject, and snippet preview
  - Returns "No relevant recent emails found." when empty

### Brief Generation Updates

Updated `/server/src/jarvis_server/meetings/briefs.py`:

1. **BRIEF_PROMPT** now includes:
   - `## Email Highlights` section with `{email_context}` placeholder
   - Added "Email Threads" to brief generation criteria

2. **gather_meeting_context()** is now async and returns tuple:
   - Returns `(memory_context, email_context)` instead of just string
   - Extracts attendee emails from `attendees_json` for email search
   - Calls `search_emails_for_meeting()` for email context

3. **generate_pre_meeting_brief()** updated:
   - Awaits `gather_meeting_context()` for both contexts
   - Formats prompt with both `context` and `email_context`

## Architecture Notes

The email search integration follows established patterns:

1. **Dual Search Strategy**:
   - Database query for emails by attendee addresses (exact matching)
   - Semantic search for emails by topic (hybrid_search)

2. **Context Flow**:
   ```
   CalendarEvent -> gather_meeting_context() -> (memory_ctx, email_ctx)
                                                        |
   BRIEF_PROMPT.format(..., context=memory_ctx, email_context=email_ctx)
                                                        |
   LLM generates brief with both contexts
   ```

3. **Performance Considerations**:
   - Limited to 10 attendee emails per meeting
   - 30-day lookback window
   - Max 5 email results per search type

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- search_emails_for_meeting imports correctly
- BRIEF_PROMPT includes email_context placeholder
- gather_meeting_context returns both memory and email context
- Brief prompt includes email-related sections (Email Highlights, Email Threads)

## Next Phase Readiness

Phase 5 complete:
- 05-01: Gmail OAuth and models
- 05-02: Gmail sync with history API
- 05-03: Email embeddings and search
- 05-04: Email context in meeting briefs

Email communication context fully integrated into Jarvis memory and meeting preparation.
