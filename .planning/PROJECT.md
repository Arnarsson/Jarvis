# Jarvis

## What This Is

A personal AI Chief of Staff that sees everything you do, remembers everything you've discussed, knows your schedule and communications, learns your patterns over time, and progressively automates your workflows. Accessed primarily through Claude Code via MCP, with a web UI over Tailscale.

## Core Value

Never lose context. Whether you've been away 2 hours or 2 months, Jarvis can catch you up on any project, decision, or thread because it sees and remembers everything.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Foundation (v1)**
- [ ] Lightweight desktop agent captures screenshots and uploads to server
- [ ] Server processes screenshots (OCR, embeddings) without slowing desktop
- [ ] AI chat exports ingested (ChatGPT, Claude, Grok)
- [ ] Calendar and email connected (Google integrations)
- [ ] Unified search queries all memory sources
- [ ] Claude Code MCP server exposes Jarvis capabilities
- [ ] Web UI accessible over Tailscale
- [ ] Multi-device support (Linux primary, Mac secondary)

**Meeting Intelligence**
- [ ] Pre-meeting briefings surface relevant context automatically
- [ ] Screen capture during meetings enables auto-notes
- [ ] Post-meeting summaries generated with action items extracted
- [ ] Commitment tracking for things you/others said you'd do

**Never Lose Context**
- [ ] "Catch me up on X" works for any project, topic, or thread
- [ ] Complete project history across screen, AI chats, calendar, email
- [ ] Decision archaeology: "Why did we choose X?" finds the moment
- [ ] Knowledge gap detection: surfaces past research on current topics

**Predictive Workday**
- [ ] Morning briefings: day overview, priorities, unfinished threads
- [ ] Context-aware switching: "Here's where you left off on Project X"
- [ ] End-of-day summaries: accomplishments, pending items
- [ ] Focus protection: detects deep work, queues interruptions

**Learning & Adaptation**
- [ ] Style learning from draft corrections: writes more like you over time
- [ ] Communication matching: adjusts tone for different recipients
- [ ] Correction learning: improves from every fix
- [ ] Pattern detection: notices repeated workflows

**Workflow Automation**
- [ ] Routine detection: identifies repeated action sequences
- [ ] Tiered trust: suggest for new patterns, auto-execute for approved
- [ ] Post-action triggers: "After merging, update the ticket"
- [ ] Template generation: creates templates from similar emails/messages

### Out of Scope

- Slack integration — explicitly excluded per user preference
- Mobile app — web UI over Tailscale is sufficient
- Public access — Tailscale-only, no public auth system needed
- Real-time collaboration — single-user system

## Context

**Source Repositories:**
- [OpenRecall](https://github.com/Arnarsson/openrecall) — Python screen capture + OCR pipeline. Fork and adapt for server-side processing.
- [Jarvis](https://github.com/Arnarsson/Jarvis) — Python/FastAPI RAG memory system with SQLite + Qdrant. Keep as memory foundation.
- [Exec](https://github.com/Arnarsson/exec) — React/Node executive assistant. Extract Google integrations, rebuild UI as part of unified system.

**Architecture:**
```
Desktop Agents (lightweight)     Hetzner Server (brain)
├── Linux primary           →    ├── OpenRecall processing
├── Mac secondary           →    ├── Jarvis RAG memory
                                 ├── Exec integrations
                                 ├── Unified API
                                 ├── Workflow engine
                                 └── MCP server
                                      ↓
                            Claude Code + Web UI (Tailscale)
```

**AI Approach:** Hybrid
- Local/server: OCR, embeddings, bulk processing (cost-effective)
- Cloud APIs: Complex reasoning, summarization (OpenAI/Anthropic)

**Infrastructure:**
- Hetzner server (needs partitioning guidance)
- Tailscale VPN (already configured)
- Linux desktop agent first, Mac later

## Constraints

- **Privacy**: Screen captures contain sensitive data. All processing on owned infrastructure. Minimize cloud API exposure. Encryption at rest.
- **Budget**: Prefer self-hosted models where quality is acceptable. Minimize per-token API costs.
- **Performance**: Desktop agent must not slow the machine. Capture and upload only, processing on server.
- **Tech stack**: Python for backend (aligns with OpenRecall + Jarvis). Web UI tech TBD based on research.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork + unify existing repos | Preserves working code, faster than rebuild | — Pending |
| Hetzner central brain | Multi-device support, keeps desktops lightweight | — Pending |
| Tailscale-only access | Privacy-critical, no need for public auth | — Pending |
| Claude Code as primary UI | Already in workflow, natural language interface | — Pending |
| Tiered trust for automation | Balances convenience with control | — Pending |
| Hybrid AI (local + cloud) | Cost-effective for bulk, quality for reasoning | — Pending |

---
*Last updated: 2026-01-24 after initialization*
