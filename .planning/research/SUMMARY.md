# Project Research Summary

**Project:** Jarvis - Personal AI Chief of Staff
**Domain:** Personal AI Assistant / Screen Recall / Workflow Automation
**Researched:** 2026-01-24
**Confidence:** MEDIUM-HIGH

## Executive Summary

Jarvis sits at the intersection of three established product categories: screen recall (pioneered by Rewind.ai, now productized by Microsoft Recall 2.0), meeting intelligence (Read.ai, Fireflies), and workflow automation (Lindy, Motion). The unique value proposition is synthesizing these capabilities in a privacy-first, local-first architecture accessible via Claude Code MCP.

The recommended approach uses battle-tested technologies designed for this exact use case: FastAPI backend on a Hetzner server, Qdrant for vector storage, Ollama for local embeddings, and lightweight desktop agents that offload heavy processing to the server. This architecture prioritizes privacy without sacrificing capability. The critical insight from research is that screen capture systems fail on **security** (Microsoft Recall's privacy disaster) and **resource management** (desktop agents that cripple user machines), not on core functionality. Both must be non-negotiable from Phase 1.

The primary risks are: (1) privacy exposure through unencrypted screenshot storage, (2) MCP server becoming an attack vector for credential theft, (3) RAG retrieval quality degrading at scale, and (4) desktop agent resource starvation. All four have proven mitigation strategies from production systems, but they must be designed into the architecture from the start, not retrofitted later.

## Key Findings

### Recommended Stack

The stack prioritizes privacy-first, self-hosted components running on owned infrastructure (Hetzner server) while supporting lightweight desktop agents. Research confirms FastAPI + Qdrant + Ollama as the industry-standard combination for personal RAG systems in 2026.

**Core technologies:**
- **FastAPI (0.128.0+)**: REST API & WebSocket server — Industry standard with massive ecosystem, forking existing Jarvis RAG project already uses it, Pydantic v2 integration for robust validation
- **Qdrant (1.16.3+)**: Vector storage — Best self-hosted option for scale (handles millions of vectors), beats Chroma on production readiness and Milvus on operational simplicity
- **Ollama + nomic-embed-text-v2-moe**: Local embeddings — State-of-the-art multilingual model (100 languages), complete privacy, zero ongoing costs, 768 dimensions with 8192 token context
- **Surya OCR**: Primary OCR engine — 97.7% accuracy vs Tesseract's 87.7%, GPU-accelerated, supports 90+ languages and layout analysis
- **MCP Python SDK (1.25.0)**: Official Anthropic MCP implementation — Stable v1.x for production, exposes tools/resources/prompts to Claude Code
- **Tailscale**: Secure mesh network — Zero-config VPN connecting desktop agents to Hetzner server without exposing ports
- **PostgreSQL (16+)**: Relational metadata — Handles concurrent writes from workers, mature HA/backup tooling; SQLite insufficient for multi-worker server
- **Celery + Redis**: Background task queue — Industry standard for async Python tasks (OCR, embeddings, workflow automation)

**Critical stack decisions:**
- Use Qdrant from start, not pgvector (performance cliff beyond 10M vectors; screen captures will exceed this within a year)
- Fork OpenRecall for desktop agent (Python-based, simpler than Screenpipe's Rust/TypeScript ecosystem)
- React + TypeScript for web UI (forking Exec dashboard which is React-based; largest ecosystem for hiring/components)
- Start with SQLite for simple metadata, migrate to PostgreSQL when concurrent writes become an issue (likely by Phase 3)

### Expected Features

Research shows the screen recall category has matured significantly since Rewind.ai's discontinuation. Microsoft Recall 2.0, Screenpipe, and OpenRecall have established baseline user expectations. Meeting intelligence is now table stakes following widespread adoption of Fireflies/Read.ai. The differentiator opportunity lies in synthesizing these with workflow automation in a "Chief of Staff" framing.

**Must have (table stakes):**
- **Screen Capture & Recording** — Core value prop; periodic screenshots with OCR extraction and local storage
- **Semantic Search** — Users expect natural language queries ("show me the PDF about X"), not just keyword search
- **Local-First Processing** — Privacy concerns dominate; Microsoft Recall backlash proved data must stay on-device/self-hosted
- **Meeting Transcription** — Speech-to-text with speaker diarization; every meeting tool offers this now
- **Meeting Summaries & Action Items** — LLM-generated summaries; standard in Fireflies/Read.ai/Otter
- **Calendar Integration** — Two-way sync with Google/Outlook; can't manage time without calendar access
- **Data Encryption** — Security table stakes after Recall controversy; encryption at rest with biometric authentication
- **User Control & Deletion** — GDPR-era expectation; users must own their data, delete snapshots, pause recording
- **AI Chat Interface** — ChatGPT/Claude normalized conversational AI; natural language interface to query captured data
- **Persistent Memory** — All major LLMs rolling this out; baseline expectation by 2026

**Should have (competitive differentiators):**
- **Pre-Meeting Intelligence Briefings** — Auto-pull context from past interactions, notes, emails about attendees/topics before meetings start
- **Proactive Follow-Up Automation** — AI drafts and sends follow-ups, updates notes; Lindy differentiates here
- **Cross-Tool Memory Graph** — Knowledge graph connecting email, calendar, screen, meetings; Mem.ai pioneered this
- **Context-Aware Workflow Triggers** — "When I see X, do Y" automation based on screen content; Screenpipe "pipes" concept
- **Learning & Adaptation Over Time** — Gets smarter about preferences and work patterns through feedback loops
- **Offline Capability** — Full functionality without internet; critical for privacy-conscious users

**Defer (v2+):**
- Real-time meeting coaching (High complexity; requires stable foundation first)
- Predictive task scheduling (Motion does this well; consider integration vs build)
- Multi-model AI selection (Nice-to-have; defer until core works)
- Mobile support (Platform complexity; focus desktop first)
- Plugin ecosystem (Need users before building extensibility)
- Cross-platform memory portability (Emerging 2026 trend; defer until local system stable)

### Architecture Approach

The architecture follows established patterns from personal AI infrastructure and screen capture pipelines, adapted for privacy-critical personal data. It separates concerns between lightweight desktop agents (capture only), central processing server (OCR/RAG/AI), and client interfaces (MCP/Web UI).

**Major components:**
1. **Desktop Agents (Linux/Mac)** — Periodic screen capture, change detection, compression, upload queue with SQLite cache; lightweight daemon that doesn't impact user's main work
2. **Central Server (Hetzner)** — FastAPI gateway routing to service layer (Memory, Capture, Workflow, Integrations); Celery workers for async processing (OCR, embeddings, syncs); event-driven ingestion with backpressure signaling
3. **Data Layer** — PostgreSQL for relational metadata, Qdrant for vector storage, file storage for compressed screenshots; separation allows independent scaling of workloads
4. **Processing Pipeline** — Async event-driven: capture → upload → OCR worker → embedding worker → searchable in Qdrant; synchronous RAG queries with hybrid search (semantic + keyword + temporal)
5. **MCP Server** — Exposes tools (search_memory, catch_me_up, list_workflows) and resources (chat history, captures, calendar) to Claude Code via stdio transport
6. **Workflow Engine** — Background pattern detection, tiered trust model (observe/suggest/auto), execution with audit logging; prevents automation trust collapse through gradual promotion

**Critical architecture patterns:**
- **Hybrid search mandatory**: Combine Qdrant semantic vectors with PostgreSQL full-text search and metadata filtering; prevents RAG quality collapse
- **Event-driven ingestion with backpressure**: Desktop agents slow capture rate if server queue fills; prevents memory exhaustion
- **Tiered trust for automation**: Three levels (observe-only, suggest, auto-execute) prevent false positive tax that destroys user trust
- **Server-side heavy processing**: OCR and embeddings run on Hetzner server with GPU, not on desktop; preserves desktop performance
- **Offline-first desktop agents**: Local SQLite queue with retry logic; never lose captures due to network issues

### Critical Pitfalls

Research identified five critical pitfalls that cause rewrites, security breaches, or project failure. All have real-world examples from Microsoft Recall, MCP security research, and production RAG systems.

1. **The Microsoft Recall Privacy Trap** — Unencrypted screenshot storage with no sensitive data filtering creates searchable database of passwords, credit cards, private messages. Microsoft postponed Recall for 6 months after security researchers demonstrated extraction with simple tools. **Mitigation**: Encryption at rest from day one (TPM + biometric authentication), sensitive content regex filtering BEFORE storage, application exclusions for password managers/banking, opt-in only with explicit consent.

2. **MCP Server as Attack Vector** — MCP servers become highest-value target; compromising one server grants access to all connected OAuth tokens (Gmail, Drive, Calendar), enabling cross-service attacks. **Mitigation**: Build your own MCP servers (never third-party for sensitive integrations), strict input validation to prevent prompt injection, token isolation per integration, human-in-the-loop mandatory for destructive actions, cryptographic server verification.

3. **RAG Retrieval Quality Collapse at Scale** — Naive vector similarity without metadata/timestamps retrieves wrong documents or outdated information, leading to hallucinated responses users trust. **Mitigation**: Hybrid search mandatory (semantic + BM25 keyword + metadata filtering + recency), timestamp everything with data freshness pipeline, chunking strategy testing (512-1536 tokens typical), evaluation framework with domain-specific known-good queries.

4. **Automation Trust Collapse (False Positive Tax)** — Over-aggressive automation executes wrong actions or floods false positives, destroying user trust; once lost, users disable automation entirely. 72% of security teams report false positives damage productivity. **Mitigation**: Tiered trust model (observe → suggest → auto-execute based on track record), precision over recall, destructive action blocks (never auto-execute deletions/payments), undo capability for 24 hours, track false positive rate and suspend above threshold.

5. **Desktop Agent Resource Starvation** — Screen capture and OCR consume so much CPU/memory that user's main work suffers; system becomes unusable. **Mitigation**: Adaptive capture frequency (event-driven when screen changes, not fixed interval), async processing pipeline (never block UI), resource budgets with hard limits on CPU%/memory, heavy OCR/LLM on server not desktop, idle-first processing.

**Additional moderate pitfalls to watch:**
- Vector storage cost explosion (prevent with INT8 quantization, 512-1536 dimension limit, data lifecycle)
- OCR accuracy cliff (use cloud OCR for complex layouts, test on real screenshots with dark mode/small fonts)
- Google API quota hell (understand tiers, implement exponential backoff, request increases early)
- Multi-device sync conflicts (UUIDs, vector clocks, offline-first, checkpoint system)
- Hetzner bandwidth surprise (choose EU datacenter for 20TB vs 1TB included bandwidth)

## Implications for Roadmap

Based on research findings and dependency analysis, the roadmap should follow this phase structure to avoid pitfalls and deliver incremental value:

### Phase 1: Privacy-First Capture Foundation
**Rationale:** Security and privacy cannot be retrofitted. Microsoft Recall's privacy disaster proves this must be foundational. Desktop agent resource management is also architectural, not additive.

**Delivers:**
- Lightweight desktop agent with adaptive screen capture
- Encrypted local storage with biometric access
- Upload queue with offline support
- Change detection to minimize redundant captures
- Server infrastructure (Hetzner, Tailscale, Docker)

**Addresses (features):**
- Screen Capture & Recording (table stakes)
- Local-First Processing (table stakes)
- Data Encryption (table stakes)
- User Control & Deletion (table stakes)

**Avoids (pitfalls):**
- Privacy exposure (encryption from day one)
- Resource starvation (adaptive capture, async processing, resource budgets)
- Infrastructure costs (EU Hetzner region, compression in transit)

**Non-negotiable requirements:**
- Encryption at rest with TPM + biometric authentication
- Sensitive content filtering (regex for credit cards, passwords, API keys)
- Application exclusion list (password managers, banking apps)
- Resource budgets (hard CPU%/memory limits)

### Phase 2: Searchable Memory (RAG Core)
**Rationale:** Provides first user-facing value. Screen capture without search is useless. Must implement hybrid search from start to avoid quality collapse.

**Delivers:**
- OCR pipeline (Surya primary, Tesseract fallback)
- Embedding generation (Ollama + nomic-embed-text)
- Qdrant vector storage with hybrid search
- PostgreSQL metadata with full-text search
- Basic FastAPI REST endpoints
- Celery workers for async processing

**Uses (stack):**
- Qdrant for vector storage (not pgvector — avoid performance cliff)
- Surya OCR with GPU acceleration (97.7% accuracy)
- Ollama for local embeddings (zero cost, privacy-preserving)
- PostgreSQL for metadata (concurrent writes from workers)
- Celery + Redis for task queue

**Implements (architecture):**
- Async event-driven ingestion (capture → OCR → embed → index)
- Hybrid search (semantic + keyword + temporal filtering)
- Reciprocal rank fusion for re-ranking
- Context assembly with token budgets

**Avoids (pitfalls):**
- RAG quality collapse (hybrid search, metadata filtering, evaluation framework)
- Vector storage bloat (INT8 quantization, dimension limits, retention policy)
- OCR accuracy cliff (Surya for accuracy, test on real screenshots)

**Research flags:**
- Deep dive on optimal chunk size for screen content (test 512, 1024, 1536 tokens)
- Validate Surya OCR accuracy on real desktop screenshots (dark mode, code, tables)

### Phase 3: MCP Server & Claude Code Integration
**Rationale:** MCP is the primary interface for Jarvis. Builds on searchable memory to expose capabilities to Claude Code.

**Delivers:**
- MCP server with stdio transport
- Tools: search_memory, catch_me_up, recall_context
- Resources: screen_captures, chat_history (if imported)
- Basic prompts for context injection
- Security hardening (input validation, token isolation)

**Uses (stack):**
- MCP Python SDK 1.25.0 (stable v1.x)
- FastMCP 2.x (cleaner API than raw SDK)

**Addresses (features):**
- AI Chat Interface (table stakes)
- Persistent Memory (table stakes)
- Semantic Search (table stakes)

**Avoids (pitfalls):**
- MCP server attack vector (build your own, strict input validation, never third-party)
- Token theft (OAuth token isolation per integration)
- Prompt injection (filter inputs for dangerous patterns)

**Non-negotiable security:**
- Human-in-the-loop for all MCP tool invocations (at least initially)
- Cryptographic server verification
- Session ID security (never in URLs or logs)
- Audit log of all MCP tool calls

### Phase 4: Calendar & Meeting Intelligence
**Rationale:** Meeting intelligence is table stakes and high-value. Calendar integration enables time-based context and pre-meeting briefs (key differentiator).

**Delivers:**
- Google Calendar integration (OAuth, two-way sync)
- Meeting detection from calendar
- Audio capture (microphone access)
- Speech-to-text transcription (Whisper or cloud)
- Meeting summaries & action items (LLM-generated)
- Pre-meeting intelligence briefs (context assembly from captures/emails/notes)

**Addresses (features):**
- Calendar Integration (table stakes)
- Meeting Transcription (table stakes)
- Meeting Summaries & Action Items (table stakes)
- Pre-Meeting Intelligence Briefings (differentiator!)

**Avoids (pitfalls):**
- Google API quota hell (understand tiers, exponential backoff, request increases early)
- OAuth token refresh failures (proactive validation, graceful re-auth UX)

**Research flags:**
- Audio transcription stack decision (Whisper vs cloud APIs for accuracy/privacy tradeoff)
- Google Calendar API quota planning (per-user limits, batch request opportunities)
- Speaker diarization requirements (Whisper large-v3 vs cloud APIs)

### Phase 5: Email & Communication Context
**Rationale:** Email context enriches pre-meeting briefs and memory graph. Gmail API well-documented with established patterns.

**Delivers:**
- Gmail integration (OAuth, read-only access)
- Email import to vector database
- Basic email triage (prioritization, flagging)
- Email context in memory search
- Communication sentiment analysis (optional)

**Addresses (features):**
- Basic Email Triage (table stakes)
- Cross-Tool Memory Graph (differentiator — connecting email, calendar, screen)

**Avoids (pitfalls):**
- Quota limits (batch requests, caching, monitoring)
- Token refresh failures (proactive validation)

### Phase 6: Workflow Automation Engine
**Rationale:** Advanced feature requiring rich data foundation. Pattern detection needs usage history. Trust model must be proven before auto-execution.

**Delivers:**
- Background pattern detection (action sequence clustering)
- Workflow template generation
- Tiered trust system (observe/suggest/auto)
- Execution engine with audit logging
- MCP tools for workflow management
- Human approval flow for high-stakes actions

**Addresses (features):**
- Context-Aware Workflow Triggers (differentiator)
- Proactive Follow-Up Automation (differentiator)
- Learning & Adaptation Over Time (differentiator)

**Avoids (pitfalls):**
- Trust collapse from false positives (precision over recall, tiered trust)
- Destructive action disasters (never auto-execute deletions/payments)

**Non-negotiable design:**
- Start all workflows in "observe" tier
- Require explicit user promotion to "suggest" then "auto"
- Track false positive rate; suspend automation above threshold
- Undo capability for 24 hours minimum
- Audit log of all automated actions

### Phase 7: Web UI & Visualization
**Rationale:** Secondary interface after MCP. Provides visual timeline and settings management. Defer to ensure core MCP experience solid first.

**Delivers:**
- React + TypeScript dashboard
- Timeline view of captures
- Search interface
- Settings (exclusions, capture frequency, trust tiers)
- Tailscale auth or network trust model

**Uses (stack):**
- React 19.x + TypeScript 5.x
- Tailwind CSS 4.x for styling
- shadcn/ui component library

**Addresses:**
- Visual context browsing
- User control over capture settings
- Workflow approval interface

### Phase Ordering Rationale

**Why this order:**
1. **Security first** — Encryption and privacy cannot be added later (Microsoft Recall lesson)
2. **Data foundation before features** — Searchable memory required before any intelligence features
3. **MCP before Web UI** — Primary interface is Claude Code; web UI is secondary
4. **Integrations after core** — Calendar/email enrich context but aren't foundational
5. **Automation last** — Needs rich data and usage patterns; highest complexity and risk

**Dependency chain:**
- Phase 1 → Phase 2: Can't search without captures
- Phase 2 → Phase 3: MCP exposes memory; needs something to expose
- Phase 3 → Phase 4: Pre-meeting briefs need MCP context assembly
- Phase 4 → Phase 5: Meeting intelligence works standalone; email enriches but isn't required
- Phase 2-5 → Phase 6: Workflow automation needs all data sources to detect patterns

**Pitfall avoidance strategy:**
- Critical pitfalls (privacy, MCP security, resource starvation) addressed in Phase 1-3
- RAG quality built into Phase 2 architecture (can't retrofit hybrid search)
- Trust model designed before automation features (Phase 6 implements, but architecture decided Phase 1)

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 2 (RAG Core):** Chunk size optimization for screen content, Surya OCR validation on real data
- **Phase 4 (Meeting Intelligence):** Audio transcription stack (Whisper vs cloud tradeoff), speaker diarization requirements
- **Phase 6 (Workflow Automation):** Pattern detection algorithms, trust tier promotion logic

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Capture Foundation):** Desktop agent patterns well-documented (OpenRecall, Screenpipe)
- **Phase 3 (MCP Server):** MCP SDK examples and official docs comprehensive
- **Phase 5 (Email Integration):** Gmail API well-documented with established OAuth patterns
- **Phase 7 (Web UI):** React admin dashboards have standard patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | FastAPI/Qdrant/Ollama verified across multiple production systems; official docs comprehensive; version compatibility confirmed |
| Features | MEDIUM-HIGH | Screen recall and meeting intelligence categories well-established; differentiator opportunities validated by Mem.ai/Lindy examples; some novel synthesis |
| Architecture | MEDIUM-HIGH | Patterns verified from personal AI infrastructure projects and RAG production systems; specific Jarvis constraints require adaptation |
| Pitfalls | HIGH | Microsoft Recall security analysis from official sources; MCP vulnerabilities from Palo Alto/Red Hat; RAG failures from academic research; all have real-world examples |

**Overall confidence:** MEDIUM-HIGH

Research is thorough with multiple source cross-validation. Stack decisions have high confidence from official docs and production deployments. Architecture patterns are proven but will need Jarvis-specific tuning. Pitfalls have real-world post-mortems providing clear prevention strategies.

### Gaps to Address

Areas where research was inconclusive or needs validation during implementation:

- **Audio transcription stack**: Whisper vs cloud APIs for accuracy/privacy/cost tradeoff — needs testing with real meeting audio to compare quality
- **Chunk size for screen content**: Research suggests 512-1536 tokens, but screen captures differ from documents — requires experimentation with real OCR output
- **Desktop agent performance**: Actual CPU/memory impact at various capture intervals unknown — needs profiling on target Linux/Mac systems
- **Calendar provider specifics**: Research covered Google Calendar; Outlook/Exchange integration may have different patterns — research when implementing
- **Workflow pattern detection algorithms**: High-level concept validated, but specific clustering/detection algorithms need research in Phase 6
- **Multi-device sync**: Deferred to post-v1, but will need CRDT research when building — conflict resolution strategy TBD

## Sources

### Primary (HIGH confidence)
- **Official Documentation**: FastAPI Release Notes, MCP Python SDK (v1.25.0), Qdrant Releases (v1.16.3), Nomic Embed v2, Surya OCR, Ollama Embedding Models, Microsoft Recall Privacy Controls, Google Cloud API Quotas, Tailscale Security Hardening
- **Security Research**: DoublePulsar Microsoft Recall Security Analysis, Palo Alto Unit 42 MCP Attack Vectors, Red Hat MCP Security Risks, MCP Official Security Best Practices
- **Technical Deep Dives**: Seven Failure Points in RAG (arXiv), Production-Grade RAG Architecture, OCR Benchmark 2026 (AIMultiple), pgvector vs Qdrant Benchmark

### Secondary (MEDIUM confidence)
- **Product Analysis**: Rewind Discontinuation (9to5Mac), Microsoft Recall Privacy (TechTarget), AI Meeting Assistants 2026 (Reclaim), Notion 3.0 AI Agents, Mem AI Features, Motion vs Reclaim comparison
- **Technical Guides**: FastAPI + Celery Guide (TestDriven.io), Multi-Device Data Sync Design (Medium), RAG Best Practices (Orkes, Kapa.ai), Vector Database Comparison (Firecrawl), Hetzner Cloud Review 2026
- **Industry Trends**: Context as 2026 AI Enabler, AI Personal Assistants 2026, Best AI Memory Extensions 2026, Workflow Automation Trends 2026

### Tertiary (LOW confidence — needs validation)
- Specific accuracy numbers for Surya OCR (97.7%) should be validated on real Jarvis screen captures
- Desktop agent resource usage estimates need profiling on target systems
- Hetzner bandwidth calculations based on compressed screenshot size assumptions

---

**Research completed:** 2026-01-24
**Ready for roadmap:** Yes
**Next step:** Roadmap creation with phase structure based on findings above
