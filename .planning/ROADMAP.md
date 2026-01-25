# Roadmap: Jarvis - Personal AI Chief of Staff

## Overview

Jarvis delivers on its core promise of "never lose context" through a seven-phase build progressing from privacy-first capture infrastructure through searchable memory, Claude Code integration, calendar/email intelligence, workflow automation, and finally a web UI. Each phase builds on the previous, with security and privacy established as non-negotiable foundations in Phase 1 rather than retrofitted later.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Privacy-First Capture Foundation** - Desktop agent captures screens, server infrastructure deployed, security foundations established
- [x] **Phase 2: Searchable Memory (RAG Core)** - OCR pipeline processes captures, embeddings enable semantic search across all content
- [x] **Phase 3: MCP Server & Claude Code** - Claude Code can query Jarvis memory and get caught up on any topic
- [ ] **Phase 4: Calendar & Meeting Intelligence** - Calendar sync enables meeting detection, audio transcription, summaries and pre-meeting briefs
- [ ] **Phase 5: Email & Communication Context** - Email context integrated into memory and pre-meeting briefs
- [ ] **Phase 6: Workflow Automation Engine** - Pattern detection identifies repeated workflows, tiered trust enables safe automation
- [ ] **Phase 7: Web UI & Visualization** - Browser dashboard for timeline browsing, search, settings, and workflow management

## Phase Details

### Phase 1: Privacy-First Capture Foundation
**Goal**: User's screen activity is captured, encrypted, and uploaded to a secure server without impacting desktop performance
**Depends on**: Nothing (first phase)
**Requirements**: CAPT-01, CAPT-02, CAPT-03, CAPT-04, CAPT-05, CAPT-06, SEC-01, SEC-02, SEC-03, SEC-04, INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. User can start the desktop agent and see screenshots being captured at configurable intervals
  2. User can pause/resume capture at any time via system tray or CLI
  3. Sensitive applications (password managers, banking) are excluded from capture
  4. Desktop performance is not noticeably degraded while agent runs
  5. Captures are uploaded to server over encrypted Tailscale connection and stored securely
**Plans**: 13 plans in 6 waves

Plans:
- [x] 01-01-PLAN.md — Agent project foundation (pyproject, config, exclusions)
- [x] 01-02-PLAN.md — Server project foundation (FastAPI, SQLAlchemy, config)
- [x] 01-03-PLAN.md — Core screenshot capture with change detection
- [x] 01-04-PLAN.md — Database schema and filesystem storage
- [x] 01-05-PLAN.md — Idle detection and window monitoring
- [x] 01-06-PLAN.md — Server upload API endpoint
- [x] 01-07-PLAN.md — Agent-server sync with retry queue
- [x] 01-08-PLAN.md — Capture engine integration (orchestrator)
- [x] 01-09-PLAN.md — System tray interface
- [x] 01-10-PLAN.md — CLI interface with exclusion wizard
- [x] 01-11-PLAN.md — Security foundations (logging, PII detection)
- [x] 01-12-PLAN.md — Docker infrastructure
- [x] 01-13-PLAN.md — End-to-end verification (checkpoint)

### Phase 2: Searchable Memory (RAG Core)
**Goal**: User can search all captured content using natural language and browse visual history
**Depends on**: Phase 1
**Requirements**: OCR-01, OCR-02, OCR-03, OCR-04, SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05
**Success Criteria** (what must be TRUE):
  1. User can query captured content with natural language and receive relevant results
  2. Search combines semantic understanding with keyword matching and time filtering
  3. AI chat exports (ChatGPT, Claude, Grok) can be imported and searched
  4. Processing pipeline handles backlog without blocking new captures
  5. Timeline browsing shows visual history of captures
**Plans**: 9 plans in 3 waves

Plans:
- [x] 02-01-PLAN.md — Redis infrastructure and Qdrant hybrid collection setup
- [x] 02-02-PLAN.md — OCR and embedding processors (EasyOCR, FastEmbed)
- [x] 02-03-PLAN.md — ARQ background processing pipeline
- [x] 02-04-PLAN.md — Hybrid search API with RRF fusion
- [x] 02-05-PLAN.md — Upload integration with processing queue
- [x] 02-06-PLAN.md — Chat export parsers (ChatGPT, Claude, Grok)
- [x] 02-07-PLAN.md — Chat import API and database storage
- [x] 02-08-PLAN.md — Timeline browsing API
- [x] 02-09-PLAN.md — Integration and end-to-end verification (checkpoint)

### Phase 3: MCP Server & Claude Code
**Goal**: Claude Code can access Jarvis memory through MCP tools
**Depends on**: Phase 2
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05
**Success Criteria** (what must be TRUE):
  1. User can invoke search_memory tool in Claude Code to query all memory sources
  2. User can invoke catch_me_up tool to get context recovery on any project or topic
  3. MCP server connects via stdio transport and appears in Claude Code tool list
  4. All MCP calls are logged in audit trail
  5. Input validation prevents prompt injection attacks
**Plans**: 5 plans in 3 waves

Plans:
- [x] 03-01-PLAN.md — MCP package foundation (pyproject.toml, FastMCP server, HTTP client)
- [x] 03-02-PLAN.md — Input validators and audit logging infrastructure
- [x] 03-03-PLAN.md — search_memory tool implementation
- [x] 03-04-PLAN.md — catch_me_up tool implementation
- [x] 03-05-PLAN.md — Integration testing and Claude Code configuration (checkpoint)

### Phase 4: Calendar & Meeting Intelligence
**Goal**: User receives pre-meeting briefs and post-meeting summaries with action items
**Depends on**: Phase 3
**Requirements**: CAL-01, CAL-02, CAL-03, CAL-04, CAL-05, CAL-06
**Success Criteria** (what must be TRUE):
  1. Google Calendar syncs with two-way event access visible in Jarvis
  2. Pre-meeting briefs auto-generated with relevant context from memory
  3. Meeting detection identifies when user is in a meeting
  4. Meeting audio is transcribed with speech-to-text
  5. Post-meeting summaries are generated with action items extracted
**Plans**: 9 plans in 4 waves

Plans:
- [ ] 04-01-PLAN.md — Google Calendar OAuth foundation and database schema
- [ ] 04-02-PLAN.md — Calendar incremental sync service
- [ ] 04-03-PLAN.md — Meeting detection via window title patterns
- [ ] 04-04-PLAN.md — Pre-meeting brief generation with memory search
- [ ] 04-05-PLAN.md — Meeting audio capture with consent gate
- [ ] 04-06-PLAN.md — Speech-to-text transcription (faster-whisper)
- [ ] 04-07-PLAN.md — Meeting summarization with action item extraction
- [ ] 04-08-PLAN.md — MCP tools for calendar and meetings
- [ ] 04-09-PLAN.md — End-to-end verification and integration testing (checkpoint)

### Phase 5: Email & Communication Context
**Goal**: Email context is integrated into memory and enriches pre-meeting briefs
**Depends on**: Phase 4
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03
**Success Criteria** (what must be TRUE):
  1. Gmail read access imports email context into Jarvis memory
  2. Email content is searchable alongside other memory sources
  3. Relevant emails are included in pre-meeting briefs for attendees and topics
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Workflow Automation Engine
**Goal**: User's repeated workflows are detected and can be automated with tiered trust levels
**Depends on**: Phase 5
**Requirements**: AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05, AUTO-06, AUTO-07
**Success Criteria** (what must be TRUE):
  1. Pattern detection identifies repeated action sequences from usage history
  2. Suggest mode proposes automations for user approval before any execution
  3. Approved workflows can be promoted to auto-execute mode
  4. Destructive actions never auto-execute without human approval
  5. User can undo automated actions for 24 hours
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

### Phase 7: Web UI & Visualization
**Goal**: User can access Jarvis through a web dashboard over Tailscale
**Depends on**: Phase 2 (search), Phase 6 (workflows)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):
  1. Web dashboard is accessible via browser over Tailscale VPN
  2. Timeline view shows visual history of captures
  3. Settings management allows configuring capture frequency, exclusions, and automation tiers
  4. Search interface enables manual queries with filter controls
  5. Workflow approval interface shows suggested automations for review
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Privacy-First Capture Foundation | 13/13 | **Complete** | 2026-01-24 |
| 2. Searchable Memory (RAG Core) | 9/9 | **Complete** | 2026-01-25 |
| 3. MCP Server & Claude Code | 5/5 | **Complete** | 2026-01-25 |
| 4. Calendar & Meeting Intelligence | 0/9 | **Planned** | - |
| 5. Email & Communication Context | 0/TBD | Not started | - |
| 6. Workflow Automation Engine | 0/TBD | Not started | - |
| 7. Web UI & Visualization | 0/TBD | Not started | - |

---
*Roadmap created: 2026-01-24*
*Phase 1 planned: 2026-01-24*
*Phase 1 completed: 2026-01-24*
*Phase 2 planned: 2026-01-24*
*Phase 2 completed: 2026-01-25*
*Phase 3 planned: 2026-01-25*
*Phase 3 completed: 2026-01-25*
*Phase 4 planned: 2026-01-25*
*Coverage: 50/50 v1 requirements mapped*
