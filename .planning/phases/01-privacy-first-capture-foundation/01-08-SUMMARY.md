---
phase: 01-privacy-first-capture-foundation
plan: 08
subsystem: agent-engine
tags: [python, async, capture-loop, orchestration, integration]

# Dependency graph
requires:
  - phase: 01-03
    provides: ScreenCapture, ChangeDetector for screenshot and change detection
  - phase: 01-05
    provides: IdleDetector, WindowMonitor, ExclusionFilter for privacy
  - phase: 01-07
    provides: CaptureUploader, UploadQueue for sync
provides:
  - CaptureLoop integrating all capture components
  - CaptureOrchestrator as main entry point for CLI/tray
  - Unified status interface for monitoring
affects: [01-09, CLI, tray-application]

# Tech tracking
tech-stack:
  added: []
  patterns: [callback-pattern, background-worker, graceful-shutdown]

key-files:
  created:
    - agent/src/jarvis/engine/__init__.py
    - agent/src/jarvis/engine/capture_loop.py
    - agent/src/jarvis/engine/orchestrator.py
  modified: []

key-decisions:
  - "1-second tick loop with ChangeDetector controlling actual captures"
  - "Standard logging instead of structlog (avoid new dependency)"
  - "Dated directory structure for captures (YYYY/MM/DD/HHMMSS_monitor.jpg)"
  - "Callback pattern for capture/skip/state events"
  - "Background upload worker with 5-second batch interval"

patterns-established:
  - "Engine module as integration layer between components"
  - "Orchestrator as main entry point for applications"
  - "Graceful shutdown with resource cleanup"

# Metrics
duration: 4min
completed: 2026-01-24
---

# Phase 01 Plan 08: Capture Engine Integration Summary

**CaptureLoop and CaptureOrchestrator unifying screenshot capture, change detection, idle monitoring, exclusion filtering, and upload queuing into a cohesive system**

## Performance

- **Duration:** 3m 52s
- **Started:** 2026-01-24T20:51:57Z
- **Completed:** 2026-01-24T20:55:49Z
- **Tasks:** 2/2
- **Files created:** 3

## Accomplishments

- CaptureLoop class integrates ScreenCapture, ChangeDetector, IdleDetector, WindowMonitor, and ExclusionFilter
- CaptureState enum (RUNNING, PAUSED, STOPPED) for lifecycle management
- CaptureResult dataclass provides structured capture data
- Callback system for capture/skip/state change events
- 1-second tick loop with ChangeDetector hybrid trigger logic
- CaptureOrchestrator coordinates capture loop, local storage, and upload queue
- Dated directory structure for local capture storage
- Background upload worker processes pending items every 5 seconds
- Unified status interface with state, queue stats, and capture count
- Pause/resume/stop lifecycle management
- Force sync capability for immediate upload attempts

## Task Commits

Each task was committed atomically:

1. **Task 1: Main capture loop** - `b7633c4` (feat)
2. **Task 2: Capture orchestrator** - `9ace48d` (feat)

## Files Created/Modified

- `agent/src/jarvis/engine/__init__.py` - Module exports (CaptureLoop, CaptureOrchestrator, CaptureState, CaptureResult)
- `agent/src/jarvis/engine/capture_loop.py` - CaptureLoop class integrating all capture components
- `agent/src/jarvis/engine/orchestrator.py` - CaptureOrchestrator coordinating capture, storage, and upload

## Decisions Made

- **1-second tick loop:** The loop runs on a 1-second tick but ChangeDetector determines if actual captures happen, allowing responsive pause/resume while respecting hybrid trigger logic
- **Standard logging over structlog:** Used Python's built-in logging to avoid adding a new dependency; structlog was mentioned in plan but not in project dependencies
- **Dated directory structure:** Captures saved as `YYYY/MM/DD/HHMMSS_monitor.jpg` for easy archival and cleanup
- **Callback pattern:** Allows flexible integration with CLI, tray, or other applications
- **Background upload worker:** 5-second interval balances responsiveness with resource usage

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed structlog dependency**
- **Found during:** Task 2
- **Issue:** Plan mentioned structlog for logging but it was not in dependencies
- **Fix:** Used standard Python logging module instead
- **Files modified:** agent/src/jarvis/engine/orchestrator.py

## Issues Encountered

None - all components integrated cleanly.

## User Setup Required

None - no external service configuration required.

## Verification Results

| Check | Result |
|-------|--------|
| CaptureLoop imports and initializes | PASS |
| CaptureLoop has idle detector | PASS |
| CaptureLoop has exclusion filter | PASS |
| CaptureOrchestrator imports and initializes | PASS |
| Orchestrator has all components wired | PASS |
| Status interface provides queue stats | PASS |

## Success Criteria Verification

| Criteria | Status |
|----------|--------|
| CAPT-01: Continuous capture at configured interval | PASS (via CaptureLoop + ChangeDetector) |
| CAPT-02: Change detection skips redundant captures | PASS (ChangeDetector hybrid trigger) |
| CAPT-03: Exclusion rules enforced | PASS (ExclusionFilter integration) |
| CAPT-05: Idle detection pauses capture | PASS (IdleDetector integration) |
| CAPT-06: Captures queued for upload | PASS (UploadQueue integration) |

## Next Phase Readiness

- Engine module ready for CLI and tray integration
- CaptureOrchestrator is the main entry point for applications
- Can be imported: `from jarvis.engine import CaptureOrchestrator`
- Status interface provides all monitoring data needed for tray icon
- Next: 01-09 will build system tray interface using this orchestrator

---
*Phase: 01-privacy-first-capture-foundation*
*Completed: 2026-01-24*
