---
phase: 04
plan: 03
subsystem: meeting-detection
tags: [meeting, window-monitoring, detection, api]

dependency_graph:
  requires: [04-01]
  provides: [meeting-detector, meetings-api, meeting-integration]
  affects: [04-04, 04-05, 04-06]

tech_stack:
  added: []
  patterns:
    - pattern-matching-detection: "Regex patterns on window titles for meeting detection"
    - background-worker: "Async worker for meeting state monitoring"
    - state-machine: "Meeting state transitions (not-in-meeting -> in-meeting -> ended)"

key_files:
  created:
    - agent/src/jarvis/meeting/__init__.py
    - agent/src/jarvis/meeting/detector.py
    - server/src/jarvis_server/api/meetings.py
  modified:
    - agent/src/jarvis/engine/orchestrator.py
    - server/src/jarvis_server/main.py

decisions:
  - id: meeting-patterns
    choice: "Regex patterns for Zoom, Google Meet, Teams detection"
    reason: "Flexible matching on window titles and app names"
  - id: meeting-worker-interval
    choice: "2-second check interval for meeting detection"
    reason: "Balanced between responsiveness and CPU usage"
  - id: calendar-correlation
    choice: "15-minute window for meeting-to-calendar correlation"
    reason: "Accounts for meetings starting early or late"

metrics:
  duration: 4 min
  completed: 2026-01-25
---

# Phase 04 Plan 03: Meeting Detection via Window Title Patterns Summary

Window-based meeting detection with agent integration and server API for lifecycle management.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create meeting detector module | 8bc16c0 | meeting/__init__.py, meeting/detector.py |
| 2 | Create meetings API on server | 55430f4 | api/meetings.py, main.py |
| 3 | Integrate meeting detector into orchestrator | 0ed2491 | engine/orchestrator.py |

## Implementation Details

### Meeting Detector (Agent)

The `MeetingDetector` class uses regex pattern matching on window titles and app names to detect meetings:

**Patterns detected:**
- Zoom: `zoom\s*(meeting|webinar)?`, `zoom\.us`
- Google Meet: `meet\.google\.com`, `google\s+meet`
- Microsoft Teams: `microsoft\s+teams`, `\|\s*meeting\s*\|.*teams`
- Generic: `(meeting|call)\s+with`

**State machine:**
- Tracks `in_meeting` boolean, `platform` enum, `started_at` timestamp, `window_title`
- Detects transitions: start, end, title changes during meeting
- Logs meeting start/end with duration

### Meetings API (Server)

**Endpoints:**
- `POST /api/meetings/start` - Record meeting start, correlate with calendar events
- `POST /api/meetings/end` - Record meeting end
- `GET /api/meetings/current` - Get active meeting (if any)
- `GET /api/meetings/{id}` - Get meeting by ID

**Calendar correlation:** Searches for CalendarEvent within 15 minutes of detected meeting start time.

### Orchestrator Integration (Agent)

**New components:**
- `_meeting_detector`: MeetingDetector instance
- `_meeting_task`: Background async task for meeting monitoring
- `_current_meeting_id`: Tracks server-assigned meeting ID

**Background worker (`_meeting_worker`):**
- Runs every 2 seconds
- Gets active window via WindowMonitor
- Checks for meeting state transitions
- Reports start/end to server via httpx

**Status reporting:** Meeting state added to `get_status()` output.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

1. Meeting detector import works
2. Platform detection verified (Zoom, Google Meet, Teams)
3. Meetings router endpoints present (/start, /end, /current, /{id})
4. Orchestrator checks window info for meetings

## Next Phase Readiness

### For 04-04 (Audio Recording)
- Meeting state available via `_meeting_detector.current_state`
- Server meeting ID tracked for associating recordings

### For 04-05 (Transcription)
- Meeting records created with `transcript_status` field
- Ready for transcript attachment after recording

### For 04-06 (Pre-meeting Briefs)
- Calendar event correlation in place
- Meeting record ready for brief attachment
