---
phase: 07-web-ui-visualization
plan: 01
title: Frontend project setup
subsystem: web-ui
tags: [htmx, jinja2, tailwindcss, alpinejs, fastapi]

# Dependency graph
requires: []
provides:
  - web-ui-foundation
  - htmx-templates
  - static-file-serving
affects:
  - 07-02 (timeline page)
  - 07-03 (calendar page)
  - 07-04 (search page)

# Tech tracking
tech-stack:
  added:
    - jinja2 (templates)
    - tailwindcss-cdn (styling)
    - htmx (dynamic UI)
    - alpinejs (client state)
  patterns:
    - HTMX fragments for partial updates
    - Jinja2 template inheritance
    - CDN-based CSS/JS (no build step)

# Key files
key-files:
  created:
    - server/src/jarvis_server/web/__init__.py
    - server/src/jarvis_server/web/routes.py
    - server/src/jarvis_server/web/api.py
    - server/src/jarvis_server/web/templates/base.html
    - server/src/jarvis_server/web/templates/index.html
    - server/src/jarvis_server/web/templates/timeline.html
    - server/src/jarvis_server/web/templates/search.html
    - server/src/jarvis_server/web/templates/calendar.html
    - server/src/jarvis_server/web/templates/settings.html
    - server/src/jarvis_server/web/templates/partials/stats.html
    - server/src/jarvis_server/web/templates/partials/upcoming-meetings.html
    - server/src/jarvis_server/web/templates/partials/recent-captures.html
    - server/src/jarvis_server/web/static/css/custom.css
  modified:
    - server/pyproject.toml
    - server/src/jarvis_server/main.py

# Decisions made
decisions:
  - id: tailwind-cdn
    choice: TailwindCSS via CDN
    why: No build step, simple setup, sufficient for MVP
  - id: htmx-fragments
    choice: HTMX for partial page updates
    why: Server-rendered HTML, minimal JS, clean patterns
  - id: alpinejs-state
    choice: Alpine.js for client-side state
    why: Lightweight, declarative, works well with HTMX

# Metrics
metrics:
  duration: 7 min
  completed: 2026-01-25
---

# Phase 07 Plan 01: Frontend Project Setup Summary

**One-liner:** Web UI foundation with HTMX + Jinja2 + TailwindCSS CDN, no build step required.

## What Was Built

Created complete web UI infrastructure:

1. **Web module** (`server/src/jarvis_server/web/`)
   - Page routes for dashboard, timeline, search, calendar, settings
   - API endpoints for HTMX fragment loading
   - Template directory with Jinja2 templates

2. **Base template** (`base.html`)
   - TailwindCSS CDN for styling
   - HTMX for dynamic interactions
   - Alpine.js for minimal client-side state
   - Responsive sidebar navigation
   - Mobile-friendly with slide-out menu
   - HTMX loading indicator

3. **Dashboard page** (`index.html`)
   - Stats cards (total captures, today's captures, events, transcribed meetings)
   - Upcoming meetings section
   - Recent captures grid
   - Quick search form
   - All sections load via HTMX fragments

4. **Stub pages** for timeline, search, calendar, settings
   - Placeholder UI ready for implementation in subsequent plans

5. **Custom CSS** (`custom.css`)
   - Navigation link styles
   - HTMX loading indicator
   - Capture thumbnail grid
   - Timeline view styles
   - Stats cards, meeting list, search results
   - Modal overlay and empty states

6. **HTMX API endpoints**
   - GET /api/web/stats - dashboard stats cards
   - GET /api/web/upcoming-meetings - meetings list
   - GET /api/web/recent-captures - capture grid

## Technical Approach

**No build step required:**
- All CSS/JS served via CDN (TailwindCSS, HTMX, Alpine.js)
- Static files mounted at /static
- Captures directory mounted at /captures

**HTMX pattern for dynamic content:**
- Server renders HTML fragments
- HTMX loads fragments into page
- Skeleton loading states while fetching

**Template inheritance:**
- base.html provides layout, nav, scripts
- Page templates extend base and fill content block
- Partials for reusable HTMX fragments

## Key Files

| File | Purpose |
|------|---------|
| `web/routes.py` | HTML page routes |
| `web/api.py` | HTMX fragment API |
| `web/templates/base.html` | Base layout template |
| `web/templates/index.html` | Dashboard page |
| `web/static/css/custom.css` | Custom styles |

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TailwindCSS delivery | CDN | No build step needed, sufficient for MVP |
| Dynamic content | HTMX fragments | Server-rendered, progressive enhancement |
| Client state | Alpine.js | Lightweight, declarative, HTMX-friendly |
| Template engine | Jinja2 | Already in FastAPI, familiar syntax |

## Verification Status

- [x] Web router imports successfully
- [x] All page routes registered (/, /timeline, /search, /calendar, /settings)
- [x] Web API routes registered (/api/web/stats, etc.)
- [x] Static files mounted at /static
- [x] All 6 page templates created
- [x] All 3 partial templates created
- [x] Custom CSS file created

## Next Phase Readiness

**Ready for:**
- 07-02: Timeline page implementation (full timeline grid with date navigation)
- 07-03: Calendar page implementation (event list, sync status)
- 07-04: Search page implementation (semantic search with filters)

**Prerequisites satisfied:**
- Base template provides consistent layout
- Navigation links already point to all pages
- HTMX infrastructure ready for dynamic loading
- Custom CSS classes defined for UI components

## Commits

| Hash | Message |
|------|---------|
| e3c5162 | chore(07-01): add jinja2 dependency for web UI templates |
| 9ab6180 | feat(07-01): create web module with page routes |
| 78fd55e | feat(07-01): create base HTML template with HTMX and TailwindCSS |
| 7e8f8c4 | feat(07-01): create dashboard index page |
| 574e94d | feat(07-01): create stub pages for timeline, search, calendar, settings |
| d29b641 | feat(07-01): create custom CSS for web UI components |
| 23e7172 | feat(07-01): mount web router and static files in FastAPI |
| 68bb1a7 | feat(07-01): create web API for dashboard HTMX fragments |
