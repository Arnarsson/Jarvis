# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-26)

**Core value:** Never lose context — whether away 2 hours or 2 months, Jarvis catches you up on any project, decision, or thread.
**Current focus:** Phase 9: Brain Timeline + Deep Memory

## Current Position

Phase: 9 (Brain Timeline + Deep Memory)
Status: In progress — memory pipeline code complete, awaiting deploy
Last activity: 2026-01-26 — Evening session: Daily 3, Bridge API, Deep Memory Pipeline, Brain Timeline vision

Progress: [####################] 100% (Phases 1-8 complete)
Phase 9: [####░░░░░░░░░░░░░░░░] 20% (code written, not deployed)

## What's Deployed (Live at jarvis.eureka-ai.cc)

- **9 Dashboard Pages:** Overview, Memory, Schedule, Comms, Tasks/Automations, Command, System, Daily 3, Focus
- **Backend:** FastAPI + PostgreSQL + Qdrant + Redis, Docker Compose
- **Email:** 763 emails synced, categorized (priority/newsletters/notifications)
- **Calendar:** Google Calendar synced, pre-meeting briefs
- **Memory:** 5,110 conversations (3,802 ChatGPT + 1,238 Claude) as single vectors
- **OCR:** 70 screen captures processed (PSM 3, Tesseract)
- **Automation:** Pattern detection (trust tiers), suppressed REPETITIVE_ACTION until OCR reliable
- **Daily 3:** AI-generated priority suggestions from calendar + emails + follow-ups
- **Clawd Dashboard:** dashboard.eureka-ai.cc (terminal viewers, workers, system status)

## What's Code-Complete But Not Deployed

### Bridge API (bridge.py — 502 lines)
- `/api/v2/bridge/search` — semantic search (PATCHED: .payload → .text_preview)
- `/api/v2/bridge/briefing` — daily briefing
- `/api/v2/bridge/decisions` — pending decisions
- `/api/v2/bridge/followups` — follow-up detection (PATCHED: timezone import)
- `/api/v2/bridge/context/<project>` — project aggregation

### Deep Memory Pipeline (4 files, ~700 lines)
- `memory/chunker.py` — splits conversations into ~500 token chunks
- `memory/tagger.py` — extracts people, projects, decisions, action items, topics
- `memory/indexer.py` — batch processor, creates `memory_chunks` Qdrant collection
- `api/memory_timeline.py` — 3 endpoints: timeline, search, stats

## Next Deploy Steps
1. `docker compose build --no-cache server` (picks up all new files)
2. `docker compose up -d` (restart)
3. Run indexer: `docker compose exec server python -m jarvis_server.memory.indexer`
4. Test: before/after search quality comparison

## Phase 9: Brain Timeline + Deep Memory

### Vision
"I never want to forget a thing again" — Sven

### Three Layers
1. **Conversation Import Pipeline** — drop ChatGPT/Claude JSONs, auto-chunk+tag+index
2. **Brain Timeline** — visual timeline by month showing projects, decisions, people, topics
3. **Unfinished Business Detector** — cross-references GitHub (50 repos, 30+ stale), emails, conversations
   - Monday report: unfinished projects, broken promises, quiet repos

### Sub-features
- Memory chunking: 5,040 conversations → ~75,000 chunks with rich metadata
- Heuristic tagging: people, projects, decisions, action items, topics, sentiment
- Timeline API: filter by date range, type, tags
- Enhanced search: granular chunk-level results vs current whole-conversation
- GitHub integration: `gh repo list` cross-referenced with conversation history
- Proactive alerts: "you discussed X but never finished it"

## Architecture Notes
- Server source: `/home/sven/Documents/jarvis/server/src/jarvis_server/`
- Frontend source: `/home/sven/Documents/jarvis/jarvis-dashboard/src/`
- Docker: `server/docker-compose.yml` — server has NO source volume mount → requires build
- DB: PostgreSQL (user=jarvis, pass=changeme, host=postgres)
- Vectors: Qdrant (collections: captures, memory_chunks)
- Embeddings: all-MiniLM-L6-v2 (384 dims)
- Mason (coding agent): builds code, Eureka reviews + deploys

## Session Continuity

Last session: 2026-01-26T18:30:00Z
Current: Brain Timeline vision defined, memory pipeline code complete
Next: Deploy everything, run indexer, test search quality, build timeline UI
