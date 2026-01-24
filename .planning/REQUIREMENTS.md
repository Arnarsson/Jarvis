# Requirements: Jarvis

**Defined:** 2026-01-24
**Core Value:** Never lose context — whether away 2 hours or 2 months, Jarvis catches you up on any project, decision, or thread.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Screen Capture

- [ ] **CAPT-01**: System captures periodic screenshots at configurable intervals
- [ ] **CAPT-02**: Change detection skips redundant captures when screen unchanged
- [ ] **CAPT-03**: Application exclusions skip specified apps (password managers, banking)
- [ ] **CAPT-04**: User can pause/resume capture at any time
- [ ] **CAPT-05**: Lightweight desktop agent does not noticeably slow machine
- [ ] **CAPT-06**: Captures upload to central server for processing

### OCR & Processing

- [ ] **OCR-01**: Screenshots processed with OCR to extract text
- [ ] **OCR-02**: OCR runs on server (not desktop) to preserve performance
- [ ] **OCR-03**: Extracted text embedded and indexed for search
- [ ] **OCR-04**: Processing pipeline handles backlog without blocking new captures

### Search & Memory

- [ ] **SRCH-01**: Semantic search returns relevant results from natural language queries
- [ ] **SRCH-02**: Hybrid search combines semantic + keyword + temporal filtering
- [ ] **SRCH-03**: AI chat exports imported (ChatGPT, Claude, Grok formats)
- [ ] **SRCH-04**: Timeline browsing shows visual history of captures
- [ ] **SRCH-05**: Search works across all memory sources (screen, chats, calendar, email)

### Security & Privacy

- [ ] **SEC-01**: Sensitive content filtering detects/masks passwords, credit cards, API keys
- [ ] **SEC-02**: Audit logging tracks all system actions and queries
- [ ] **SEC-03**: All traffic between agent and server encrypted in transit (Tailscale)
- [ ] **SEC-04**: Server accessible only via Tailscale VPN (no public exposure)

### MCP & Claude Code

- [ ] **MCP-01**: MCP server exposes `search_memory` tool for querying all sources
- [ ] **MCP-02**: MCP server exposes `catch_me_up` tool for context recovery on any topic
- [ ] **MCP-03**: MCP server connects via stdio transport to Claude Code
- [ ] **MCP-04**: MCP calls logged in audit trail
- [ ] **MCP-05**: Input validation prevents prompt injection attacks

### Calendar & Meetings

- [ ] **CAL-01**: Google Calendar syncs with two-way event access
- [ ] **CAL-02**: Pre-meeting briefs auto-generated with relevant context from memory
- [ ] **CAL-03**: Meeting detection identifies when user is in a meeting
- [ ] **CAL-04**: Audio capture records meeting audio (with user consent)
- [ ] **CAL-05**: Speech-to-text transcribes meeting audio
- [ ] **CAL-06**: Meeting summaries generated with action items extracted

### Email

- [ ] **EMAIL-01**: Gmail read access imports email context
- [ ] **EMAIL-02**: Email content searchable from Jarvis
- [ ] **EMAIL-03**: Relevant emails included in pre-meeting briefs

### Workflow Automation

- [ ] **AUTO-01**: Pattern detection identifies repeated action sequences
- [ ] **AUTO-02**: Suggest mode proposes automations for user approval
- [ ] **AUTO-03**: Auto-execute mode runs approved workflows automatically
- [ ] **AUTO-04**: Tiered trust system (observe → suggest → auto) with explicit promotion
- [ ] **AUTO-05**: Destructive actions never auto-execute (require human approval)
- [ ] **AUTO-06**: False positive tracking suspends automation above threshold
- [ ] **AUTO-07**: Undo capability for 24 hours on automated actions

### User Interface

- [ ] **UI-01**: Web dashboard accessible via browser over Tailscale
- [ ] **UI-02**: Timeline view shows visual history of captures
- [ ] **UI-03**: Settings management for capture config, exclusions, automation tiers
- [ ] **UI-04**: Search interface for manual queries
- [ ] **UI-05**: Workflow approval interface for reviewing suggested automations

### Infrastructure

- [ ] **INFRA-01**: Hetzner server hosts all backend services
- [ ] **INFRA-02**: Tailscale mesh connects desktop agents to server
- [ ] **INFRA-03**: Desktop agent runs on Linux
- [ ] **INFRA-04**: Desktop agent runs on Mac (secondary)
- [ ] **INFRA-05**: Server partitioning documented and implemented

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced Security

- **SEC-V2-01**: Encryption at rest with biometric authentication
- **SEC-V2-02**: User data deletion (full wipe capability)
- **SEC-V2-03**: Application-level encryption for stored screenshots

### Enhanced MCP

- **MCP-V2-01**: `recall_context` tool for specific time range queries
- **MCP-V2-02**: Resource exposure for captures and chat history
- **MCP-V2-03**: Custom prompts for domain-specific context injection

### Advanced Intelligence

- **INT-V2-01**: Predictive task scheduling based on patterns
- **INT-V2-02**: Communication style matching for different recipients
- **INT-V2-03**: Knowledge gap detection (surfaces past research on current topics)
- **INT-V2-04**: Decision archaeology (find when/why decisions were made)

### Additional Integrations

- **INTEG-V2-01**: Outlook/Exchange calendar support
- **INTEG-V2-02**: Notion/Obsidian knowledge base sync
- **INTEG-V2-03**: Browser extension for richer page capture

### Mobile & Multi-device

- **MULTI-V2-01**: Mobile web UI optimization
- **MULTI-V2-02**: Multi-device sync with conflict resolution
- **MULTI-V2-03**: Cross-device continuity ("continue where I left off")

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Slack integration | User preference — explicitly excluded |
| Real-time meeting coaching | High complexity, defer to v2+ |
| Mobile native app | Web UI over Tailscale is sufficient |
| Public access / auth system | Tailscale-only access, no public exposure needed |
| Multi-model AI selection | Nice-to-have, defer until core works |
| Plugin ecosystem | Need users before building extensibility |
| OAuth providers beyond Google | Gmail/Calendar sufficient for v1 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAPT-01 | TBD | Pending |
| CAPT-02 | TBD | Pending |
| CAPT-03 | TBD | Pending |
| CAPT-04 | TBD | Pending |
| CAPT-05 | TBD | Pending |
| CAPT-06 | TBD | Pending |
| OCR-01 | TBD | Pending |
| OCR-02 | TBD | Pending |
| OCR-03 | TBD | Pending |
| OCR-04 | TBD | Pending |
| SRCH-01 | TBD | Pending |
| SRCH-02 | TBD | Pending |
| SRCH-03 | TBD | Pending |
| SRCH-04 | TBD | Pending |
| SRCH-05 | TBD | Pending |
| SEC-01 | TBD | Pending |
| SEC-02 | TBD | Pending |
| SEC-03 | TBD | Pending |
| SEC-04 | TBD | Pending |
| MCP-01 | TBD | Pending |
| MCP-02 | TBD | Pending |
| MCP-03 | TBD | Pending |
| MCP-04 | TBD | Pending |
| MCP-05 | TBD | Pending |
| CAL-01 | TBD | Pending |
| CAL-02 | TBD | Pending |
| CAL-03 | TBD | Pending |
| CAL-04 | TBD | Pending |
| CAL-05 | TBD | Pending |
| CAL-06 | TBD | Pending |
| EMAIL-01 | TBD | Pending |
| EMAIL-02 | TBD | Pending |
| EMAIL-03 | TBD | Pending |
| AUTO-01 | TBD | Pending |
| AUTO-02 | TBD | Pending |
| AUTO-03 | TBD | Pending |
| AUTO-04 | TBD | Pending |
| AUTO-05 | TBD | Pending |
| AUTO-06 | TBD | Pending |
| AUTO-07 | TBD | Pending |
| UI-01 | TBD | Pending |
| UI-02 | TBD | Pending |
| UI-03 | TBD | Pending |
| UI-04 | TBD | Pending |
| UI-05 | TBD | Pending |
| INFRA-01 | TBD | Pending |
| INFRA-02 | TBD | Pending |
| INFRA-03 | TBD | Pending |
| INFRA-04 | TBD | Pending |
| INFRA-05 | TBD | Pending |

**Coverage:**
- v1 requirements: 45 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 45

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-24 after initial definition*
