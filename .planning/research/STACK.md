# Technology Stack

**Project:** Jarvis - Personal AI Chief of Staff
**Researched:** 2026-01-24
**Overall Confidence:** MEDIUM-HIGH

## Executive Summary

This stack prioritizes privacy-first, self-hosted components that run efficiently on owned infrastructure (Hetzner server) while supporting lightweight desktop agents on Linux/Mac. The architecture separates concerns: desktop agents capture screen/audio locally, a central FastAPI server handles RAG/memory, and Claude Code connects via MCP.

---

## Recommended Stack

### Core Backend Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **FastAPI** | 0.128.0+ | REST API & WebSocket server | Industry standard for async Python APIs. Massive ecosystem, extensive documentation, easy hiring. Pydantic v2 integration provides robust validation. While Litestar is ~2x faster in benchmarks, FastAPI's ecosystem maturity and community support outweigh raw performance for this use case. | HIGH |
| **Uvicorn** | 0.34.0+ | ASGI server | Default FastAPI server, production-ready with gunicorn workers | HIGH |
| **Pydantic** | 2.10.0+ | Data validation | Required by FastAPI, excellent for settings management and API schemas | HIGH |
| **Python** | 3.11+ | Runtime | OpenRecall requires 3.11. FastAPI/MCP require 3.10+. Use 3.11 for compatibility and performance. | HIGH |

**Rationale:** FastAPI over Litestar because:
- You're forking existing FastAPI-based projects (Jarvis RAG)
- Community support matters more than 2x benchmark performance for a personal tool
- MCP SDK examples all use FastAPI patterns

### Vector Database

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Qdrant** | 1.16.3+ | Vector storage & similarity search | Best balance of performance, features, and operational simplicity for self-hosted. Written in Rust, supports hybrid search (dense + sparse vectors), excellent metadata filtering. Beats Milvus on ops simplicity, beats Chroma on scale. | HIGH |

**Alternatives Considered:**

| Option | Why Not |
|--------|---------|
| Chroma | Excellent for prototyping but explicitly "not designed for production workloads at 50M+ vectors." You'll exceed 10M vectors within a year of screen capture. |
| Milvus | More powerful but requires Kubernetes and "data engineering muscle." Overkill for single-user system. |
| pgvector | Good if you need relational + vector, but Qdrant's filtering and performance are superior for pure RAG. |

**Deployment:** Docker container on Hetzner server. ~2GB RAM for millions of vectors.

```bash
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant:v1.16.3
```

### OCR Solutions

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Surya OCR** | Latest | Primary OCR for screen captures | 97.7% accuracy vs Tesseract's 87.7% in benchmarks. Supports 90+ languages, layout analysis, table recognition. GPU-accelerated. | MEDIUM-HIGH |
| **Tesseract** | 5.x | Fallback / CPU-only environments | Battle-tested, CPU-friendly, good for clean text. Use when GPU unavailable. | HIGH |

**Rationale:** Surya is the clear winner for accuracy, but:
- Requires GPU for optimal performance (your Hetzner server should have one)
- GPL license - acceptable for personal use
- Desktop agents should send screenshots to server for Surya processing, not run OCR locally

**NOT recommended:**
- EasyOCR: Lowest accuracy in benchmarks despite being popular
- Cloud APIs (AWS Textract, Google Vision): Violates privacy-first constraint

### Embedding Models

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **nomic-embed-text-v2-moe** | Latest | Primary embeddings | State-of-the-art multilingual (100 languages), 768 dimensions, 8192 token context. Matryoshka support for dimension reduction. Beats BGE-M3 on MIRACL benchmark. | HIGH |
| **Ollama** | Latest | Local model serving | Zero-cost, complete privacy, easy management. Serves nomic-embed-text locally. | HIGH |

**Alternative for resource-constrained environments:**

| Model | Dimensions | Use Case |
|-------|------------|----------|
| all-minilm | 384 | Fast prototyping, limited RAM |
| mxbai-embed-large | 1024 | Maximum accuracy when resources available |

**Deployment via Ollama:**
```bash
ollama pull nomic-embed-text
# API available at http://localhost:11434/api/embed
```

**NOT recommended:**
- OpenAI embeddings: Privacy violation, ongoing costs
- Cohere embeddings: Same issues

### MCP Server Implementation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **MCP Python SDK** | 1.25.0 | Official MCP implementation | Official Anthropic SDK. Stable v1.x recommended for production (v2 coming Q1 2026). Supports stdio, SSE, HTTP transports. | HIGH |
| **FastMCP** | 2.x (stable) | Simplified MCP development | "Powers 70% of MCP servers." Cleaner API than raw SDK. Use FastMCP 2.x for production, not 3.0 beta. | MEDIUM-HIGH |

**Installation:**
```bash
pip install "mcp[cli]"  # Official SDK
# OR
pip install 'fastmcp<3'  # FastMCP stable
```

**MCP exposes:**
- Tools: Search memory, recall context, trigger workflows
- Resources: Chat history, screen captures, calendar data
- Prompts: Context injection templates for Claude Code

### Desktop Agent (Screen Capture)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **OpenRecall** | Fork | Screen capture + local OCR | AGPLv3, cross-platform (Linux/Mac/Windows), privacy-first design. Already Python-based, easy to fork and extend. | MEDIUM-HIGH |
| **MSS** | 10.0.0+ | Screenshot library | Ultra-fast, pure Python, cross-platform. Used if building custom capture. | HIGH |
| **PyAutoGUI** | 0.9.54+ | Optional: keyboard/mouse automation | Cross-platform automation. Only if workflow automation needs input simulation. | MEDIUM |

**Architecture Decision:** Fork OpenRecall rather than build from scratch or use Screenpipe because:
- OpenRecall is pure Python (matches your stack)
- Screenpipe is Rust/TypeScript (different ecosystem)
- OpenRecall is simpler, Screenpipe is more feature-rich but heavier

**Desktop Agent should:**
1. Capture screenshots at intervals (MSS for speed)
2. Send to central server via Tailscale for Surya OCR
3. NOT run heavy OCR locally (preserves desktop performance)

### Web UI Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **React** | 19.x | Dashboard UI | You're forking Exec (React/Node). Largest ecosystem, easiest hiring, extensive component libraries. | HIGH |
| **TypeScript** | 5.x | Type safety | Required for maintainable React | HIGH |
| **Tailwind CSS** | 4.x | Styling | Utility-first, fast development | HIGH |
| **shadcn/ui** | Latest | Component library | Beautiful, accessible, copy-paste components | MEDIUM-HIGH |

**NOT Svelte because:**
- You're forking React-based Exec
- React talent pool is 5-10x larger
- React ecosystem has more admin dashboard libraries

### Infrastructure & Networking

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Tailscale** | Latest | Secure mesh network | Zero-config VPN, WireGuard-based. Desktop agents connect to Hetzner server without exposing ports. | HIGH |
| **Docker** | Latest | Containerization | Standard deployment for all services | HIGH |
| **docker-compose** | Latest | Multi-service orchestration | Simple enough for single-server deployment | HIGH |
| **Caddy** | 2.x | Reverse proxy (optional) | Automatic HTTPS, simpler than nginx. Only if exposing services beyond Tailscale. | MEDIUM |

**Tailscale Architecture:**
```
[Mac Desktop Agent] --tailscale--> [Hetzner Server]
[Linux Desktop Agent] --tailscale--> [Hetzner Server]
[Claude Code MCP] --tailscale--> [Hetzner Server]
```

### Database (Relational)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **SQLite** | 3.x | Metadata, workflow state, user data | Simple, no server needed, excellent for single-user. Use SQLAlchemy for ORM. | HIGH |
| **PostgreSQL** | 16+ | Optional: if SQLite limits hit | Only if you need concurrent writes or complex queries. Unlikely for personal assistant. | MEDIUM |

**Rationale:** Start with SQLite. Migrate to PostgreSQL only if you hit concurrent write issues (you won't for single-user).

### Task Queue (Workflow Automation)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Celery** | 5.4.0+ | Background task queue | Industry standard for Python async tasks. Workflows, scheduled jobs, email sending. | HIGH |
| **Redis** | 7.x | Celery broker + caching | Fast, simple, proven. Also useful for caching frequent queries. | HIGH |

**Alternative considered:**
- Dramatiq: Simpler than Celery but smaller ecosystem
- RQ: Too simple for workflow automation needs

### Calendar & Email Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **caldav** | 1.4.0+ | Calendar access | Standard protocol, works with Google/Outlook/self-hosted | MEDIUM |
| **exchangelib** | 5.x | Microsoft 365 integration | If using Outlook/Exchange | MEDIUM |
| **google-api-python-client** | 2.x | Google Workspace | If using Google Calendar/Gmail | MEDIUM |
| **imapclient** | 3.x | Email access | Standard IMAP, works with any provider | HIGH |

**Note:** Calendar/email integrations are highly provider-dependent. Research specific providers when implementing.

---

## Complete Installation

### Server (Hetzner)

```bash
# Python environment
pyenv install 3.11.11
pyenv local 3.11.11
python -m venv .venv
source .venv/bin/activate

# Core dependencies
pip install fastapi[standard] uvicorn[standard] pydantic pydantic-settings
pip install qdrant-client
pip install surya-ocr  # Requires GPU
pip install "mcp[cli]"
pip install celery redis
pip install sqlalchemy aiosqlite
pip install httpx  # Async HTTP client

# Embedding models via Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text

# Vector database
docker run -d --name qdrant -p 6333:6333 -v ~/qdrant_storage:/qdrant/storage qdrant/qdrant:v1.16.3

# Redis for Celery
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Desktop Agent (Linux/Mac)

```bash
# Lightweight - only capture and send
pip install mss httpx
pip install openrecall  # Or fork

# Install Tailscale
# Linux: curl -fsSL https://tailscale.com/install.sh | sh
# Mac: brew install tailscale
```

### Web UI

```bash
npx create-next-app@latest jarvis-ui --typescript --tailwind --eslint
cd jarvis-ui
npx shadcn@latest init
```

---

## Technology NOT to Use

| Technology | Why Avoid |
|------------|-----------|
| **LangChain** | Unnecessary abstraction layer. You're building a focused system, not a generic LLM app. Direct API calls are simpler and more maintainable. |
| **LlamaIndex** | Same rationale. Good for prototyping, but adds complexity for production. |
| **Django** | Too heavyweight for API-first architecture. FastAPI is better fit. |
| **Flask** | No native async support. FastAPI is strictly better for this use case. |
| **MongoDB** | No advantage over SQLite for single-user. Vector search inferior to Qdrant. |
| **EasyOCR** | Lowest accuracy in benchmarks. Use Surya or Tesseract. |
| **Electron** | Desktop app framework is overkill. Lightweight daemon + web UI is simpler. |
| **Cloud embedding APIs** | Violates privacy-first constraint. Use Ollama. |

---

## Version Pinning Strategy

Pin major versions, allow minor updates:

```toml
# pyproject.toml example
[project]
dependencies = [
    "fastapi>=0.128.0,<1.0.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.10.0,<3.0.0",
    "qdrant-client>=1.16.0,<2.0.0",
    "mcp>=1.25.0,<2.0.0",
    "celery>=5.4.0,<6.0.0",
]
```

---

## Sources

### HIGH Confidence (Official Documentation)
- FastAPI Release Notes: https://fastapi.tiangolo.com/release-notes/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk (v1.25.0, Dec 2025)
- Qdrant Releases: https://github.com/qdrant/qdrant/releases (v1.16.3, Dec 2024)
- Nomic Embed v2: https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe
- Surya OCR: https://github.com/datalab-to/surya
- MSS Documentation: https://python-mss.readthedocs.io/
- Ollama Embedding Models: https://ollama.com/blog/embedding-models

### MEDIUM Confidence (Verified WebSearch)
- Vector DB Comparison: https://www.firecrawl.dev/blog/best-vector-databases-2025
- OCR Comparison: https://modal.com/blog/8-top-open-source-ocr-models-compared
- FastAPI vs Litestar: https://betterstack.com/community/guides/scaling-python/litestar-vs-fastapi/
- Tailscale Self-Hosting: https://tailscale.com/blog/self-host-a-local-ai-stack

### LOW Confidence (Needs Validation)
- Specific accuracy numbers for Surya (97.7%) should be validated on your data
- Calendar integration libraries may have breaking changes; verify before implementing

---

## Gaps Requiring Phase-Specific Research

1. **Audio transcription**: Not covered. If adding microphone capture, research Whisper vs alternatives.
2. **Calendar provider specifics**: Research when implementing Google/Outlook integration.
3. **Workflow automation patterns**: Celery is the tool, but workflow design patterns need deeper research.
4. **Desktop agent performance**: Actual CPU/memory impact of screenshot intervals needs testing.
