# Phase 1: Privacy-First Capture Foundation - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Desktop agent captures screenshots and uploads to Hetzner server. Security foundations established: sensitive content filtering, audit logging, encrypted transport via Tailscale. Server infrastructure deployed with Docker Compose. Agent runs on Linux (primary) and Mac (secondary).

</domain>

<decisions>
## Implementation Decisions

### Capture Behavior
- Hybrid trigger: change detection + 15-second minimum interval as fallback
- Multi-monitor: capture active monitor, plus other monitors if in use
- Pause capture when machine idle (no input for 5+ minutes)
- Default interval: 15 seconds (user configurable)

### Agent Interface
- System tray + CLI dual interface
- Tray icon shows status: green=active, yellow=paused, red=error
- Right-click menu: Pause/Resume, Open settings, View recent captures, Force sync, View logs, Quit
- Configurable keyboard shortcut for pause/resume
- Minimal notifications: only errors and important state changes
- Manual start required (no auto-start on boot by default)
- CLI uses subcommand style: `jarvis capture start`, `jarvis status`, `jarvis config`
- CLI output: human-readable by default, `--json` flag for machine-readable

### Exclusion Rules
- Predefined exclusion list ships with common apps: 1Password, Bitwarden, banking apps
- Interactive wizard to configure exclusions (select from running apps)
- Matching by app name + window title (e.g., "Firefox" or "Firefox - Private Browsing")
- Exclusions are permanent (not time-based) — if in list, never capture

### Server Architecture
- Docker Compose deployment on Hetzner
- Filesystem storage with database metadata (not BLOBs or object storage)
- Captures compressed (JPEG quality ~80) on disk
- PostgreSQL for metadata, timestamps, OCR text references
- Single disk volume (Docker manages storage internally)
- Smart retention: keep important moments, compress/thin older data

### Claude's Discretion
- Exact compression quality and format
- Specific Docker service configuration
- Database schema design
- Backup strategy implementation
- Smart retention algorithm details

</decisions>

<specifics>
## Specific Ideas

- Filesystem + metadata is recommended for easier retrieval and intelligence without excessive storage
- Status indicator colors match common conventions (green/yellow/red)
- CLI should feel like familiar tools (subcommand style like git, docker)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-privacy-first-capture-foundation*
*Context gathered: 2026-01-24*
