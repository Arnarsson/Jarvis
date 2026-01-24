---
phase: 01-privacy-first-capture-foundation
plan: 05
subsystem: agent
tags: [python, pynput, pywinctl, idle-detection, window-monitoring, privacy]

# Dependency graph
requires:
  - phase: 01-01
    provides: Agent package structure and exclusions.yaml format
provides:
  - Idle detection using pynput keyboard/mouse listeners
  - Active window detection using PyWinCtl
  - Exclusion filter for privacy-sensitive applications
  - Thread-safe IdleDetector with context manager support
affects: [01-06, capture-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns: [pynput-listeners, pywinctl-active-window, exclusion-filter-pattern]

key-files:
  created:
    - agent/src/jarvis/monitor/__init__.py
    - agent/src/jarvis/monitor/idle.py
    - agent/src/jarvis/monitor/window.py
  modified: []

key-decisions:
  - "time.monotonic() for idle tracking (not affected by system clock changes)"
  - "NamedTuple for WindowInfo (immutable, hashable)"
  - "Graceful error handling returns None instead of raising"

patterns-established:
  - "IdleDetector: context manager pattern for resource cleanup"
  - "ExclusionFilter: case-insensitive substring matching"
  - "WindowMonitor: stateless, query-on-demand pattern"

# Metrics
duration: 2min
completed: 2026-01-24
---

# Phase 01 Plan 05: Idle Detection and Window Monitoring Summary

**Pynput-based idle detection and PyWinCtl window monitoring with exclusion filtering for password managers and private browsing**

## Performance

- **Duration:** 2m 12s
- **Started:** 2026-01-24T20:39:13Z
- **Completed:** 2026-01-24T20:41:25Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- IdleDetector tracks keyboard/mouse activity with configurable threshold (default 5 minutes)
- WindowMonitor detects active application name and window title using PyWinCtl
- ExclusionFilter blocks capture for password managers (1Password, Bitwarden, KeePass, etc.)
- Private browsing detection (Firefox, Chrome Incognito, Edge InPrivate)
- Thread-safe implementation with proper resource cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Idle detection with pynput** - `dfcbdb9` (feat)
2. **Task 2: Window detection and exclusion filter** - `7f50bd9` (feat)

## Files Created/Modified

- `agent/src/jarvis/monitor/__init__.py` - Module exports IdleDetector, WindowMonitor, ExclusionFilter, WindowInfo
- `agent/src/jarvis/monitor/idle.py` - IdleDetector class with pynput listeners
- `agent/src/jarvis/monitor/window.py` - WindowMonitor, WindowInfo, ExclusionFilter classes

## Decisions Made

- **time.monotonic() for timestamps:** Not affected by system clock changes or NTP adjustments
- **NamedTuple for WindowInfo:** Immutable and hashable, simple data container
- **Graceful error handling:** WindowMonitor returns None on errors (permission denied, no display)
- **No daemon threads:** Proper start/stop lifecycle for clean shutdown

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - tasks executed smoothly.

## User Setup Required

None - no external service configuration required.

Note: On macOS, the IdleDetector requires Accessibility permissions to be granted in System Preferences > Privacy & Security > Accessibility. On Linux/Wayland, some functionality may be limited.

## Next Phase Readiness

- Idle detection ready for integration with capture orchestration
- Window monitoring ready for exclusion checks before capture
- ExclusionFilter can load patterns from the existing exclusions.yaml config
- Ready for plan 01-06 (if scheduled) or capture orchestration integration

---
*Phase: 01-privacy-first-capture-foundation*
*Completed: 2026-01-24*
