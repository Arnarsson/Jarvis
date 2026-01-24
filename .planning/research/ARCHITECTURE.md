# Architecture Patterns for Jarvis

**Domain:** Personal AI Assistant with Screen Recall, RAG Memory, and Workflow Automation
**Researched:** 2026-01-24
**Confidence:** MEDIUM-HIGH (patterns verified across multiple sources; specific implementations will need validation)

## Executive Summary

Jarvis requires a distributed architecture with clear separation between lightweight desktop agents, a central processing server, and client interfaces. The architecture follows established patterns from personal AI infrastructure, screen capture pipelines, and RAG systems, adapted for the specific constraints of privacy-critical personal data and multi-device support.

The recommended architecture is **event-driven with hybrid processing** — real-time for screen capture ingestion, async batch for OCR/embedding, and request-response for retrieval/AI queries.

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ Claude Code  │    │   Web UI     │    │   Future     │                  │
│  │  (MCP)       │    │  (React)     │    │   Clients    │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘                  │
│         │                   │                                               │
│         └─────────┬─────────┘                                               │
│                   │ Tailscale VPN                                           │
└───────────────────┼─────────────────────────────────────────────────────────┘
                    │
┌───────────────────┼─────────────────────────────────────────────────────────┐
│                   │          HETZNER SERVER (Central Brain)                 │
│                   ▼                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                        API GATEWAY (FastAPI)                        │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │    │
│  │  │  REST API   │  │  MCP Server │  │  WebSocket  │  │  Health   │ │    │
│  │  │  /api/v1/*  │  │  /mcp       │  │  /ws        │  │  /health  │ │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                   │                                                          │
│  ┌────────────────┼───────────────────────────────────────────────────┐    │
│  │                ▼          SERVICE LAYER                             │    │
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐│    │
│  │  │   Memory Service  │  │  Capture Service  │  │ Workflow Engine ││    │
│  │  │  - RAG retrieval  │  │  - Upload handler │  │ - Pattern detect││    │
│  │  │  - Hybrid search  │  │  - Queue dispatch │  │ - Execution     ││    │
│  │  │  - AI summaries   │  │  - Device registry│  │ - Trust tiers   ││    │
│  │  └───────────────────┘  └───────────────────┘  └─────────────────┘│    │
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐│    │
│  │  │ Integration Svc   │  │  Calendar/Email   │  │  Briefing Svc   ││    │
│  │  │  - Chat imports   │  │  - Google APIs    │  │ - Morning brief ││    │
│  │  │  - Source parsers │  │  - Sync handlers  │  │ - Meeting prep  ││    │
│  │  └───────────────────┘  └───────────────────┘  └─────────────────┘│    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                   │                                                          │
│  ┌────────────────┼───────────────────────────────────────────────────┐    │
│  │                ▼          PROCESSING LAYER                          │    │
│  │  ┌───────────────────────────────────────────────────────────────┐ │    │
│  │  │                    Task Queue (Redis)                          │ │    │
│  │  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐  │ │    │
│  │  │   │ capture │  │   ocr   │  │ embed   │  │  scheduled      │  │ │    │
│  │  │   │  queue  │  │  queue  │  │  queue  │  │  tasks queue    │  │ │    │
│  │  │   └─────────┘  └─────────┘  └─────────┘  └─────────────────┘  │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  │                              │                                      │    │
│  │  ┌───────────────────────────┼───────────────────────────────────┐ │    │
│  │  │                    Workers (Celery)                            │ │    │
│  │  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │ │    │
│  │  │   │ OCR Worker  │  │ Embedding   │  │  Integration        │   │ │    │
│  │  │   │ (CPU/GPU)   │  │ Worker      │  │  Sync Worker        │   │ │    │
│  │  │   └─────────────┘  └─────────────┘  └─────────────────────┘   │ │    │
│  │  └───────────────────────────────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                   │                                                          │
│  ┌────────────────┼───────────────────────────────────────────────────┐    │
│  │                ▼           DATA LAYER                               │    │
│  │  ┌───────────────────┐  ┌───────────────────┐  ┌─────────────────┐│    │
│  │  │   PostgreSQL      │  │      Qdrant       │  │   File Storage  ││    │
│  │  │  - Metadata       │  │  - Vectors        │  │  - Screenshots  ││    │
│  │  │  - Relations      │  │  - Semantic search│  │  - Documents    ││    │
│  │  │  - User prefs     │  │  - Payloads       │  │  - Compressed   ││    │
│  │  │  - Audit logs     │  │                   │  │                 ││    │
│  │  └───────────────────┘  └───────────────────┘  └─────────────────┘│    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                    ▲
                    │ Upload via HTTP
┌───────────────────┼─────────────────────────────────────────────────────────┐
│                   │              DESKTOP AGENTS                             │
│  ┌────────────────┴───────────────┐    ┌────────────────────────────────┐  │
│  │         Linux Agent            │    │         Mac Agent              │  │
│  │  ┌──────────────────────────┐  │    │  ┌──────────────────────────┐  │  │
│  │  │  Screen Capture Daemon   │  │    │  │  Screen Capture Daemon   │  │  │
│  │  │  - Periodic capture      │  │    │  │  - Periodic capture      │  │  │
│  │  │  - Change detection      │  │    │  │  - Change detection      │  │  │
│  │  │  - Compression           │  │    │  │  - Compression           │  │  │
│  │  │  - Upload queue          │  │    │  │  - Upload queue          │  │  │
│  │  └──────────────────────────┘  │    │  └──────────────────────────┘  │  │
│  │  ┌──────────────────────────┐  │    │  ┌──────────────────────────┐  │  │
│  │  │  Local SQLite Cache      │  │    │  │  Local SQLite Cache      │  │  │
│  │  │  - Pending uploads       │  │    │  │  - Pending uploads       │  │  │
│  │  │  - Sync state            │  │    │  │  - Sync state            │  │  │
│  │  └──────────────────────────┘  │    │  └──────────────────────────┘  │  │
│  └────────────────────────────────┘    └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Protocol |
|-----------|---------------|-------------------|----------|
| **Desktop Agent** | Screen capture, compression, upload, offline queue | Server Capture Service | HTTPS (upload), WebSocket (status) |
| **API Gateway** | Route requests, auth, rate limiting | All services | Internal function calls |
| **MCP Server** | Expose Jarvis tools to Claude Code | Memory, Workflow, Briefing services | MCP over stdio |
| **Memory Service** | RAG retrieval, hybrid search, context assembly | PostgreSQL, Qdrant, Cloud LLMs | SQL, gRPC, REST |
| **Capture Service** | Accept uploads, dispatch to processing queue | Redis queue, File storage | Redis protocol |
| **Workflow Engine** | Pattern detection, execution, trust management | All data sources, external APIs | Internal + webhooks |
| **OCR Worker** | Image to text extraction | Redis queue, PostgreSQL | Redis protocol |
| **Embedding Worker** | Text to vector conversion | Redis queue, Qdrant | Redis protocol |
| **Integration Sync** | Poll/webhook external services | Google APIs, Chat exports | REST, OAuth |
| **PostgreSQL** | Structured data, metadata, relations | All services | SQL |
| **Qdrant** | Vector storage, semantic search | Memory Service, Embedding Worker | gRPC |
| **File Storage** | Screenshots, documents, compressed images | Capture Service, Memory Service | Filesystem |

---

## Data Flow

### Screen Capture Pipeline (Async, Event-Driven)

```
1. CAPTURE (Desktop Agent)
   └── Every N seconds (configurable, default 5s)
   └── Change detection (skip if <5% pixel diff)
   └── Compress (JPEG, quality 60-80)
   └── Queue locally if offline

2. UPLOAD (Desktop Agent → Server)
   └── HTTP POST with metadata (timestamp, device_id, window_info)
   └── Return immediately with capture_id
   └── Retry with exponential backoff on failure

3. DISPATCH (Capture Service)
   └── Write compressed image to file storage
   └── Insert capture record (status: pending)
   └── Enqueue to OCR queue

4. OCR (OCR Worker)
   └── Pull from queue (FIFO, batch capable)
   └── Run Tesseract or cloud OCR (based on config)
   └── Update capture record with extracted text
   └── Enqueue to embedding queue

5. EMBED (Embedding Worker)
   └── Pull from queue
   └── Generate embedding (local model or API)
   └── Upsert to Qdrant with payload (capture_id, timestamp, text snippet)
   └── Update capture record (status: indexed)

6. SEARCHABLE
   └── Memory Service can now retrieve via semantic search
```

### RAG Query Flow (Synchronous)

```
1. QUERY (Client via MCP or REST)
   └── "What was I working on yesterday afternoon?"

2. PARSE (Memory Service)
   └── Extract time constraints, intent, entities
   └── Determine search strategy (semantic, temporal, hybrid)

3. RETRIEVE (Memory Service → Qdrant + PostgreSQL)
   └── Semantic search in Qdrant (top-k vectors)
   └── Filter by time range in PostgreSQL
   └── Join with metadata (source type, window info)
   └── Re-rank by relevance + recency

4. ASSEMBLE (Memory Service)
   └── Collect source documents (screenshots, chat excerpts, calendar)
   └── Truncate to context window budget
   └── Format for LLM consumption

5. GENERATE (Memory Service → Cloud LLM)
   └── Send assembled context + user query
   └── Return structured response (summary + sources)
```

### Workflow Detection & Execution (Background + Triggered)

```
1. OBSERVE (Workflow Engine - Background)
   └── Consume events from all sources
   └── Build action sequences (N-grams of user actions)
   └── Cluster similar sequences

2. DETECT (Workflow Engine - Background)
   └── When pattern frequency > threshold
   └── Generate workflow template
   └── Classify: routine (>5x) vs occasional (2-4x)

3. SUGGEST (Workflow Engine - Triggered)
   └── When partial pattern match detected
   └── Check trust tier for this pattern
   └── If tier=suggest: notify user via MCP/WebSocket
   └── If tier=auto: execute without prompting

4. EXECUTE (Workflow Engine - Triggered)
   └── Run approved automation steps
   └── Log all actions for audit
   └── Handle failures gracefully (rollback or alert)
```

---

## Synchronous vs Async Decision Matrix

| Operation | Pattern | Rationale |
|-----------|---------|-----------|
| Screenshot upload | **Async** (fire-and-forget) | Desktop must not wait for processing |
| OCR processing | **Async** (queue-based) | CPU-intensive, can batch |
| Embedding generation | **Async** (queue-based) | Can lag behind capture by minutes |
| RAG query | **Sync** (request-response) | User waiting for answer |
| Workflow suggestion | **Async** (push notification) | Non-blocking |
| Workflow execution | **Async** (fire-and-forget) | May take variable time |
| Calendar/email sync | **Async** (scheduled polling) | Background, periodic |
| MCP tool calls | **Sync** (request-response) | Claude Code expects immediate response |
| Health checks | **Sync** | Needs immediate status |

---

## Data Layer Architecture

### Recommendation: PostgreSQL + Qdrant (Separate)

**Why not pgvector?**
- pgvector performance degrades beyond 10M vectors ([benchmark source](https://nirantk.com/writing/pgvector-vs-qdrant/))
- Screen captures at 5s intervals = ~17K captures/day/device
- 1 year of capture = ~6M records per device, grows quickly
- Qdrant handles billion-scale with logarithmic complexity
- Separation allows independent scaling of relational vs vector workloads

**Why not SQLite on server?**
- SQLite is single-writer, problematic with concurrent workers
- PostgreSQL handles concurrent writes from multiple workers
- PostgreSQL has mature HA, replication, backup tooling

**Why SQLite on desktop agents?**
- Perfect for local queue + sync state
- Zero-config, file-based
- Agent is single-threaded anyway

### Schema Strategy

```
PostgreSQL (Relational Truth):
├── captures (id, device_id, timestamp, status, ocr_text, metadata)
├── chat_imports (id, source, message_id, timestamp, content, embedding_id)
├── calendar_events (id, google_id, title, start, end, description)
├── emails (id, google_id, subject, from, to, timestamp, body_snippet)
├── workflows (id, name, pattern_hash, frequency, trust_tier, steps_json)
├── workflow_executions (id, workflow_id, triggered_at, status, log)
├── devices (id, name, platform, last_seen, config_json)
└── user_preferences (key, value, updated_at)

Qdrant (Vector Index):
├── captures_collection (vector, payload: {capture_id, timestamp, text_preview})
├── chats_collection (vector, payload: {import_id, source, timestamp, preview})
├── calendar_collection (vector, payload: {event_id, title, timestamp})
└── email_collection (vector, payload: {email_id, subject, timestamp})
```

### Multi-Device Sync Strategy

```
1. DEVICE REGISTRATION
   └── Agent generates UUID on first run
   └── Registers with server (device_id, platform, hostname)
   └── Server assigns sync token

2. UPLOAD DEDUPLICATION
   └── Each capture includes: device_id + local_id + timestamp
   └── Server maintains unique constraint
   └── Idempotent uploads (retry-safe)

3. CONFLICT RESOLUTION
   └── Server is source of truth for processed data
   └── Agent is source of truth for raw captures
   └── No merge conflicts (append-only capture log)

4. OFFLINE HANDLING
   └── Agent queues uploads locally in SQLite
   └── On reconnect, uploads in order (oldest first)
   └── Server processes in arrival order (eventual consistency)
```

---

## Communication Patterns

### Desktop Agent to Server

```python
# Agent uploads are fire-and-forget with local queue
# Pseudo-code for clarity

class CaptureUploader:
    def __init__(self, server_url: str, queue: LocalQueue):
        self.server_url = server_url
        self.queue = queue

    async def upload(self, capture: Capture):
        try:
            # Non-blocking upload
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/api/v1/captures",
                    files={"image": capture.compressed_bytes},
                    data={"device_id": capture.device_id,
                          "timestamp": capture.timestamp.isoformat(),
                          "window_info": json.dumps(capture.window_info)},
                    timeout=30.0
                )
                if response.status_code == 202:  # Accepted
                    self.queue.mark_uploaded(capture.local_id)
        except Exception:
            # Keep in queue, retry later
            self.queue.mark_retry(capture.local_id)
```

### Inter-Service Communication

**Recommendation: Direct function calls within monolith, queue for async**

For a single-server deployment, avoid microservice overhead:
- Services are Python modules, not separate processes
- Share database connections via connection pool
- Use Celery for truly async work (OCR, embeddings, syncs)
- Reserve HTTP/gRPC for external integrations only

```python
# Monolithic service composition
# services/__init__.py

from .memory import MemoryService
from .capture import CaptureService
from .workflow import WorkflowEngine

# Shared dependencies injected
class Services:
    def __init__(self, db: Database, vector_db: Qdrant, queue: Redis):
        self.memory = MemoryService(db, vector_db)
        self.capture = CaptureService(db, queue)
        self.workflow = WorkflowEngine(db, self.memory)
```

### MCP Server Integration

The MCP server exposes Jarvis capabilities to Claude Code:

```python
# mcp_server.py - Simplified structure

from mcp import Server, Tool

server = Server("jarvis")

@server.tool("search_memory")
async def search_memory(query: str, time_range: Optional[str] = None) -> str:
    """Search across all memory sources."""
    results = await services.memory.search(query, time_range)
    return format_results(results)

@server.tool("catch_me_up")
async def catch_me_up(topic: str) -> str:
    """Get comprehensive context on a topic."""
    context = await services.memory.assemble_context(topic)
    summary = await services.memory.summarize(context)
    return summary

@server.tool("list_workflows")
async def list_workflows() -> str:
    """List detected workflow patterns."""
    workflows = await services.workflow.list_patterns()
    return format_workflows(workflows)

@server.tool("approve_workflow")
async def approve_workflow(workflow_id: str, trust_tier: str) -> str:
    """Set trust level for a workflow pattern."""
    await services.workflow.set_trust(workflow_id, trust_tier)
    return f"Workflow {workflow_id} set to {trust_tier}"
```

---

## Patterns to Follow

### Pattern 1: Event-Driven Ingestion with Backpressure

**What:** Use bounded queues with worker pools. If queue fills, signal agents to slow capture rate.

**When:** Anytime processing can't keep up with ingestion.

**Why:** Prevents memory exhaustion, graceful degradation under load.

```python
# Redis-based queue with backpressure signaling
async def handle_capture_upload(capture_data: bytes, metadata: dict):
    queue_depth = await redis.llen("capture_queue")

    if queue_depth > MAX_QUEUE_DEPTH:
        # Signal agent to reduce capture frequency
        return JSONResponse(
            {"status": "accepted", "backpressure": True, "suggested_interval": 30},
            status_code=202
        )

    await redis.rpush("capture_queue", msgpack.packb({
        "data": capture_data,
        "metadata": metadata
    }))

    return JSONResponse({"status": "accepted"}, status_code=202)
```

### Pattern 2: Hybrid Search (Semantic + Keyword + Temporal)

**What:** Combine vector similarity with full-text search and time filtering.

**When:** RAG queries need both semantic understanding and precise matching.

**Why:** Semantic search alone misses exact terms; keyword alone misses meaning.

```python
async def hybrid_search(
    query: str,
    time_start: Optional[datetime] = None,
    time_end: Optional[datetime] = None,
    limit: int = 20
) -> List[SearchResult]:
    # 1. Semantic search (Qdrant)
    query_vector = await embed(query)
    semantic_results = await qdrant.search(
        collection="captures",
        query_vector=query_vector,
        limit=limit * 2,  # Over-fetch for re-ranking
        filter=time_filter(time_start, time_end)
    )

    # 2. Full-text search (PostgreSQL)
    keyword_results = await db.execute("""
        SELECT id, ts_rank(to_tsvector(ocr_text), plainto_tsquery($1)) as rank
        FROM captures
        WHERE to_tsvector(ocr_text) @@ plainto_tsquery($1)
        AND timestamp BETWEEN $2 AND $3
        ORDER BY rank DESC
        LIMIT $4
    """, query, time_start, time_end, limit * 2)

    # 3. Reciprocal Rank Fusion
    return reciprocal_rank_fusion(semantic_results, keyword_results, k=60)[:limit]
```

### Pattern 3: Tiered Trust for Automation

**What:** Three-tier trust system: observe-only, suggest, auto-execute.

**When:** Workflow automation with user control.

**Why:** Balances convenience with safety; builds trust over time.

```python
class TrustTier(Enum):
    OBSERVE = "observe"      # Pattern detected, no action
    SUGGEST = "suggest"      # Prompt user when pattern matches
    AUTO = "auto"            # Execute without prompting

class WorkflowEngine:
    async def on_pattern_match(self, workflow: Workflow, context: Context):
        match workflow.trust_tier:
            case TrustTier.OBSERVE:
                # Log for later review
                await self.log_observation(workflow, context)

            case TrustTier.SUGGEST:
                # Push notification to user
                await self.notify_user(
                    f"Detected pattern: {workflow.name}. Execute?",
                    actions=[
                        ("Execute", self.execute, workflow, context),
                        ("Skip", None),
                        ("Promote to Auto", self.promote, workflow)
                    ]
                )

            case TrustTier.AUTO:
                # Execute with audit log
                await self.execute_with_audit(workflow, context)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Synchronous Processing in Upload Path

**What:** Running OCR or embedding during the upload request.

**Why bad:**
- Desktop agent blocks waiting for response
- Single slow image blocks all subsequent uploads
- Timeout failures lose data

**Instead:** Accept upload immediately, queue for async processing.

### Anti-Pattern 2: Single Large Context Window

**What:** Stuffing all retrieved documents into one LLM call.

**Why bad:**
- Token limits exceeded
- Cost explosion
- Irrelevant context dilutes relevant
- "Lost in the middle" effect

**Instead:**
- Retrieve more, re-rank, select top-k
- Use Map-Reduce for large document sets
- Budget tokens per source type

### Anti-Pattern 3: Polling for Everything

**What:** Desktop agent polls server for status, WebSocket polling, etc.

**Why bad:**
- Wasted bandwidth and compute
- Stale data between polls
- Complexity in poll intervals

**Instead:**
- Push from server via WebSocket for real-time updates
- Use webhooks for external service changes
- Poll only for services without push support

### Anti-Pattern 4: Storing Vectors in PostgreSQL for Scale

**What:** Using pgvector when you expect >50M vectors.

**Why bad:**
- Performance cliff beyond 10M vectors
- HNSW index memory pressure on primary database
- Mixing vector workload with transactional workload

**Instead:** Use dedicated vector database (Qdrant) from the start. Migration is painful.

### Anti-Pattern 5: Tight Coupling to Specific LLM Provider

**What:** Hardcoding OpenAI or Anthropic API calls throughout codebase.

**Why bad:**
- Vendor lock-in
- Can't switch for cost/performance
- Testing requires API calls

**Instead:**
- Abstract LLM interface
- Support multiple backends (local, OpenAI, Anthropic)
- Use local models for tests

---

## Scalability Considerations

| Concern | Current (Single User) | 10K Captures/Day | 100K Captures/Day |
|---------|----------------------|------------------|-------------------|
| **Storage** | ~1GB/month compressed | ~10GB/month | ~100GB/month - add object storage |
| **OCR** | Single Celery worker | 2-4 workers | GPU worker or cloud OCR API |
| **Embeddings** | Local model, batched | Local model, parallel batches | Dedicated embedding service |
| **Vector DB** | Single Qdrant node | Single Qdrant node | Qdrant cluster or managed |
| **PostgreSQL** | Single instance | Single instance | Consider read replicas |
| **Queue** | Single Redis | Single Redis | Redis cluster |

**Key insight:** For a single-user personal assistant, you'll hit 100K captures/day only at ~2 second intervals across multiple devices. Current architecture handles 10K captures/day easily. Scale concerns are future problems.

---

## Suggested Build Order

Based on component dependencies:

```
Phase 1: Data Foundation
├── PostgreSQL schema + migrations
├── Qdrant collections
├── File storage structure
└── Redis setup
    Rationale: Everything depends on data layer

Phase 2: Desktop Agent (Minimal)
├── Screen capture daemon
├── Local SQLite queue
├── HTTP upload client
└── Change detection
    Rationale: Need data flowing before processing

Phase 3: Core Processing Pipeline
├── Capture Service (accept uploads)
├── OCR Worker (Celery + Tesseract)
├── Embedding Worker (Celery + local model)
└── Basic FastAPI endpoints
    Rationale: Turn raw captures into searchable data

Phase 4: Memory Service
├── Hybrid search implementation
├── Context assembly
├── LLM integration for summaries
└── REST API endpoints
    Rationale: First user-facing value

Phase 5: MCP Server
├── Tool definitions
├── Claude Code integration
└── Basic memory queries
    Rationale: Primary interface, builds on Memory Service

Phase 6: Web UI (MVP)
├── Timeline view
├── Search interface
├── Basic settings
└── Tailscale auth (or trust network)
    Rationale: Secondary interface, visual context

Phase 7: Integrations
├── Google Calendar sync
├── Google Email sync
├── Chat import parsers
└── Webhook handlers
    Rationale: Enriches context, not core functionality

Phase 8: Workflow Engine
├── Pattern detection
├── Trust tier management
├── Execution engine
├── Audit logging
└── MCP tools for workflows
    Rationale: Advanced feature, needs rich data foundation

Phase 9: Briefing Service
├── Morning briefings
├── Meeting prep
├── End-of-day summaries
└── Scheduled generation
    Rationale: Builds on all previous components
```

---

## Sources

**Architecture Patterns:**
- [AI System Design Guide 2026](https://www.systemdesignhandbook.com/guides/ai-system-design/)
- [Personal AI Infrastructure (danielmiessler)](https://github.com/danielmiessler/Personal_AI_Infrastructure)
- [LangChain Multi-Agent Architecture Guide](https://www.blog.langchain.com/choosing-the-right-multi-agent-architecture/)

**Screen Capture & OCR:**
- [HealthEdge OCR Pipeline Architecture](https://healthedge.com/resources/blog/building-a-scalable-ocr-pipeline-technical-architecture-behind-healthedge-s-document-processing-platform)
- [Dropbox OCR Pipeline](https://dropbox.tech/machine-learning/creating-a-modern-ocr-pipeline-using-computer-vision-and-deep-learning)
- [Screenpipe MCP Server](https://skywork.ai/skypage/en/screenpipe-mcp-ai-vision-memory/1978719521292800000)
- [NormCap (GitHub)](https://github.com/dynobo/normcap)

**RAG Systems:**
- [Production-Grade RAG Architecture](https://levelup.gitconnected.com/designing-a-production-grade-rag-architecture-bee5a4e4d9aa)
- [Orkes RAG Best Practices](https://orkes.io/blog/rag-best-practices/)
- [Six Lessons Building RAG in Production](https://towardsdatascience.com/six-lessons-learned-building-rag-systems-in-production/)
- [Kapa.ai RAG Best Practices](https://www.kapa.ai/blog/rag-best-practices)

**Message Queues:**
- [FastAPI + Celery + RabbitMQ](https://medium.com/cuddle-ai/async-architecture-with-fastapi-celery-and-rabbitmq-c7d029030377)
- [FastAPI Background Tasks Docs](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [TestDriven.io FastAPI + Celery Guide](https://testdriven.io/courses/fastapi-celery/intro/)

**Vector Databases:**
- [pgvector vs Qdrant Benchmark](https://nirantk.com/writing/pgvector-vs-qdrant/)
- [Best Vector Databases 2025 (Firecrawl)](https://www.firecrawl.dev/blog/best-vector-databases-2025)
- [DataCamp Vector Database Comparison](https://www.datacamp.com/blog/the-top-5-vector-databases)
- [How to Choose VectorDB (Milvus)](https://milvus.io/blog/choosing-the-right-vector-database-for-your-ai-apps.md)

**Data Sync:**
- [Multi-Device Data Sync Design](https://medium.com/@engineervishvnath/designing-a-robust-data-synchronization-system-for-multi-device-mobile-applications-c0b23e4fc0cb)
- [Offline-First Frontend Apps 2025](https://blog.logrocket.com/offline-first-frontend-apps-2025-indexeddb-sqlite/)
- [SQLite vs PostgreSQL Comparison](https://airbyte.com/data-engineering-resources/sqlite-vs-postgresql)

**MCP Integration:**
- [Model Context Protocol Docs](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Claude Code MCP Integration](https://code.claude.com/docs/en/mcp)
- [MCP Server Guide (Generect)](https://generect.com/blog/claude-mcp/)

**Workflow Automation:**
- [AI Workflow Automation Trends 2026 (Kissflow)](https://kissflow.com/workflow/7-workflow-automation-trends-every-it-leader-must-watch-in-2025/)
- [Autonomous Workflows 2026](https://what.digital/autonomous-workflows-ai-automation/)
- [n8n AI Workflow Tools](https://blog.n8n.io/best-ai-workflow-automation-tools/)

**Trust & Security:**
- [AI Agent Zero-Trust 2026](https://medium.com/@raktims2210/ai-agent-identity-zero-trust-the-2026-playbook-for-securing-autonomous-systems-in-banks-e545d077fdff)
- [AI TRiSM Guide (Palo Alto)](https://www.paloaltonetworks.com/cyberpedia/ai-trism)

**Desktop Agents:**
- [DWAgent Architecture](https://deepwiki.com/dwservice/agent)
- [Bytebot Desktop Environment](https://docs.bytebot.ai/core-concepts/desktop-environment)
- [Python Daemon on macOS](https://andypi.co.uk/2023/02/14/how-to-run-a-python-script-as-a-service-on-mac-os/)

**Event-Driven Architecture:**
- [Building Modern Data Systems (DEV)](https://dev.to/devcorner/building-modern-data-systems-event-driven-architecture-messaging-queues-batch-processing-etl--51hm)
- [Event-Driven Architecture (Confluent)](https://www.confluent.io/learn/event-driven-architecture/)
- [Data Engineering Trends 2026](https://www.trigyn.com/insights/data-engineering-trends-2026-building-foundation-ai-driven-enterprises)

**Tailscale:**
- [What is Tailscale](https://tailscale.com/kb/1151/what-is-tailscale)
- [Headscale Self-Hosted](https://github.com/juanfont/headscale)
- [Tailscale Homelab Use Case](https://tailscale.com/use-cases/homelab)
