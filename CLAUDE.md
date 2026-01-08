# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Unified Memory MCP** is a RAG (Retrieval-Augmented Generation) memory system that ingests ChatGPT, Claude, and Grok conversation exports into SQLite, creates embeddings with Qdrant, and serves them via an MCP (Model Context Protocol) server with hybrid search.

**Architecture**: Conversation exports → chat-export-structurer (vendor submodule) → SQLite → indexer.py (chunking + embedding) → Qdrant (vector DB) + SQLite FTS5 (lexical search) ← server.py (MCP endpoint with hybrid ranking)

## Core Components

### `server.py` (MCP Server)
- **Purpose**: FastMCP-based server exposing two tools: `search()` and `fetch()`
- **Key Functions**:
  - `hybrid_search()`: Combines FTS5 lexical scores (40% weight) + Qdrant semantic scores (60% weight)
  - `fts_search()`: BM25 full-text search over SQLite FTS5 virtual table, inverts BM25 to (0,1] score
  - `fetch_chunk()`: Retrieves full chunk content by ID
- **Schema**: Queries `rag_chunks` table for metadata and text
- **Transport**: Supports SSE (default), HTTP, or stdio via FastMCP
- **Response Format**: OpenAI MCP spec—JSON-encoded content in text array

### `server_http.py` (HTTP API Server)
- **Purpose**: FastAPI HTTP server for Raycast extension and direct API access
- **Key Endpoints**:
  - `GET /search?q=&time=&limit=`: Hybrid search with time filtering
  - `GET /chunk/{chunk_id}`: Fetch full chunk content
  - `POST /store`: Store new memories with entity extraction
  - `GET /entities`: List extracted entities
  - `GET /beliefs`: Get consolidated beliefs/preferences
- **Features**: CORS enabled, unified memory integration, knowledge graph support
- **Port**: Default 8000, configurable via `--port`

### `webapp.py` (Memory Explorer Web UI)
- **Purpose**: FastAPI web application for browsing and searching memories
- **Features**:
  - Hybrid search with time filters (natural language: "last week", "August 2025")
  - Quick query presets for common searches
  - Claude History Explorer integration (if available)
  - Intelligence layer for entity extraction and proactive suggestions
  - Chunk detail view with full conversation context
- **Templates**: Jinja2 templates in `web/templates/`
- **Port**: Default 5000, run with `make webapp`

### `intelligence.py` (Executive Intelligence Layer)
- **Purpose**: LLM-powered intelligence for memory analysis
- **Capabilities**:
  - `extract_entities()`: Extract people, projects, technologies, concepts from content
  - Proactive memory surfacing based on context
  - Belief/preference detection and consolidation
  - Contradiction detection across memories
  - Temporal pattern recognition
- **Model**: Uses `gpt-4o-mini` for fast, cost-effective extraction
- **Integration**: Optional—gracefully degrades if OPENAI_API_KEY not set

### `indexer.py` (Chunking + Embedding Pipeline)
- **Purpose**: Two-stage indexing: (1) chunk messages into semantic units, (2) embed chunks to Qdrant
- **Key Functions**:
  - `build_chunks()`: Groups messages by thread, applies sliding window algorithm with token limits
  - `detect_message_schema()`: Auto-detects column names from chat-export-structurer output (schema flexibility for message_id, thread_id, role, text, ts variations)
  - `embed()`: Batches chunks and calls OpenAI embeddings API, stores vectors in Qdrant
  - `token_count()`: Uses tiktoken (or fallback /4 character heuristic) for token accounting
- **Chunking Algorithm**: Sliding window with overlap—chunks up to `max_tokens` (default 1100), minimum `min_tokens` (250), with `overlap_msgs` (2) for context continuity
- **Deduplication**: SHA1-based chunk IDs prevent re-embedding identical chunks

### Database Schema
**`rag_chunks`** (main storage):
- `chunk_id` (TEXT, PK): SHA1 hash of thread_id|msg_start_id|msg_end_id|text_length
- `thread_id`, `title`, `ts_start`/`ts_end`, `msg_start_id`/`msg_end_id`: Metadata
- `token_count`: For UI/reporting
- `text`: Full chunk content
- `embedded` (INT): 0=pending embedding, 1=done
- `created_at`: Timestamp

**`rag_chunks_fts`** (virtual FTS5 table):
- Indexed columns: `chunk_id` (UNINDEXED), `title`, `text`
- Enables BM25-based full-text search

**Indexes**:
- `idx_rag_chunks_thread`: Fast thread lookup
- `idx_rag_chunks_embedded`: Fast filtering of unembedded chunks

## Development Workflow

### Setup
```bash
make setup                    # Creates .venv, installs all deps
source .venv/bin/activate
```

### Configuration
```bash
cp .env.example .env
# Edit .env with:
# - OPENAI_API_KEY (required for embeddings)
# - QDRANT_URL (default: http://localhost:6333)
# - QDRANT_COLLECTION (default: memory_chunks)
# - EMBED_MODEL (default: text-embedding-3-small)
# - PUBLIC_BASE_URL (base for chunk URLs in responses)
```

### Data Ingestion
Ingest from vendor/chat-export-structurer submodule:
```bash
make qdrant-up                # Start Qdrant Docker container
make ingest-chatgpt CHATGPT_EXPORT=/path/to/conversations.json
make ingest-anthropic ANTHROPIC_EXPORT=/path/to/conversations.json
make ingest-grok GROK_EXPORT=/path/to/export.json
```

### Chunking & Embedding
```bash
export OPENAI_API_KEY="sk-..."
make chunks                   # Run indexer.py build-chunks
make embed                    # Run indexer.py embed
make index                    # Both chunks + embed
```

Or with custom options:
```bash
python indexer.py build-chunks --db memory.sqlite --max-tokens 1100 --min-tokens 250 --overlap-msgs 2
python indexer.py embed --db memory.sqlite --batch-size 64
```

### Running the Server
```bash
make serve                    # SSE transport (default)
make serve-stdio              # Stdio transport (for MCP client integration)
make serve-http               # HTTP API server (for Raycast/direct API)
make webapp                   # Memory Explorer web UI
```

Custom args:
```bash
python server.py --db memory.sqlite --host 0.0.0.0 --port 8000 --transport sse --base-url https://my-domain.com
python server_http.py --port 8000  # HTTP API
uvicorn webapp:app --port 5000     # Web UI
```

### Cleanup
```bash
make clean                    # Removes database + stops Qdrant
```

## Key Design Decisions

### Hybrid Search Weighting
- **60% semantic** (Qdrant cosine similarity): Captures meaning and intent
- **40% lexical** (FTS5 BM25): Captures exact terms and rare tokens
- **Ranking**: Combined scores sorted descending, top-k returned

### Message Overlap in Chunks
- Default 2 messages overlapped between consecutive chunks
- Prevents context loss at chunk boundaries
- Configurable via `--overlap-msgs`

### Token-Based Chunking
- Uses tiktoken for accurate token counting (important for LLM context windows)
- Graceful fallback: `/4` character heuristic if tiktoken unavailable
- Helps size chunks appropriately for downstream LLM usage

### Schema Detection
- `indexer.py` auto-detects column names from messages table
- Supports multiple naming conventions (message_id/id, role/author_role/sender, text/content/message)
- Makes tool compatible with evolving chat-export-structurer output

### MCP Response Format
- Returns JSON-encoded content as text (per OpenAI MCP spec)
- Enables interop with Claude, ChatGPT, and other MCP clients
- search() returns lightweight summaries (id, title, url), fetch() returns full chunks

## Common Development Tasks

### Adding a New Chunking Strategy
- Modify `build_chunks()` window logic and/or overlap behavior
- Update Makefile help text if adding new indexer.py subcommands
- Ensure schema remains compatible with existing rag_chunks table

### Tuning Hybrid Search
- Edit weights in `server.py` `hybrid_search()` function (w_sem, w_lex)
- Run search tests with your query corpus to validate ranking

### Extending Schema Detection
- Add new column name variants to `detect_message_schema()` in indexer.py
- Test with vendor/chat-export-structurer output from new export formats

### Debugging Embedding Issues
- Check `embedded` column in rag_chunks: 1 = successfully embedded, 0 = pending
- Query Qdrant collection size: `curl http://localhost:6333/collections/memory_chunks | jq .result.vectors_count`
- Verify OpenAI API key and model availability

## Testing & Validation

No formal test suite currently. Validate with:
```bash
# Check database integrity
sqlite3 memory.sqlite "SELECT COUNT(*), AVG(token_count) FROM rag_chunks;"

# Verify FTS indexing
sqlite3 memory.sqlite "SELECT COUNT(*) FROM rag_chunks_fts;"

# Test MCP search endpoint (if server running on localhost:8000)
curl -X POST http://localhost:8000/search -H "Content-Type: application/json" -d '{"query": "test query"}'

# Test HTTP API endpoints
curl "http://localhost:8000/search?q=test&limit=5"
curl "http://localhost:8000/search?q=meetings&time=last%20week"
curl http://localhost:8000/entities
curl http://localhost:8000/beliefs

# Test Memory Explorer webapp
open http://localhost:5000  # Browse in browser

# Check Qdrant collection
curl http://localhost:6333/collections/memory_chunks
```

## Performance Considerations

- **Embedding batching**: Default batch_size=64 balances API throughput and memory usage
- **FTS5 performance**: Queries over rag_chunks_fts table are fast; ensure index on thread_id exists
- **Qdrant search limits**: Search queries fetch top-20 from both lexical and semantic, rank final top-8
- **Token counting**: Expensive (tiktoken encoding), but critical for chunk sizing; cached in token_count column

## Dependencies

- **fastmcp**: MCP server framework
- **fastapi**: HTTP API and webapp framework
- **uvicorn**: ASGI server for FastAPI
- **jinja2**: Template engine for webapp
- **qdrant-client**: Vector database client
- **openai**: Embeddings API and intelligence layer
- **python-dotenv**: Environment variable loading
- **tiktoken**: Token counting for LLMs
- **chat-export-structurer** (vendor): Parsing ChatGPT/Claude/Grok exports

See pyproject.toml for versions and dev dependencies (pytest, ruff).

## Repository Structure

```
.
├── server.py              # MCP server (search + fetch tools)
├── server_http.py         # HTTP API server (Raycast/direct access)
├── webapp.py              # Memory Explorer web UI
├── indexer.py             # Chunking + embedding pipeline
├── intelligence.py        # Executive intelligence layer (entity extraction, beliefs)
├── unified_memory.py      # Unified memory database with knowledge graph
├── time_filters.py        # Natural language time parsing
├── score_utils.py         # Score normalization utilities
├── cli.py                 # Command-line interface
├── Makefile               # Command shortcuts
├── pyproject.toml         # Project metadata + ruff config
├── requirements.txt       # Pip dependencies
├── .env.example           # Environment template
├── docker-compose.yml     # Qdrant container config
├── web/
│   └── templates/         # Jinja2 templates for webapp
│       ├── base.html      # Base template with styling
│       ├── index.html     # Search results page
│       ├── chunk.html     # Chunk detail view
│       └── conversation.html  # Conversation view
├── memory-raycast/        # Raycast extension for memory search
├── vendor/
│   └── chat-export-structurer/  # Submodule: export parsing
└── README.md              # User-facing docs
```

## Git Workflow

- Main branch: `claude/unified-memory-mcp-B8BDj`
- All commits should follow convention: `type: description` (feat, fix, docs, chore, etc.)
- Submodule (`vendor/chat-export-structurer`) is pinned; update with `git submodule update --remote` if needed

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Qdrant connection error | Ensure `make qdrant-up` ran; check `QDRANT_URL` in .env |
| "Missing columns" during build-chunks | Verify export format matches chat-export-structurer expectations; check messages table schema |
| OpenAI API errors during embed | Check OPENAI_API_KEY is valid and not rate-limited; verify EMBED_MODEL is available |
| FTS search returns nothing | Ensure build-chunks completed and upsert_chunk_fts() populated rag_chunks_fts |
| Low search quality | Tune hybrid search weights; increase overlap_msgs; reduce max_tokens for more granular chunks |
| Webapp templates not found | Ensure `web/templates/` directory exists with all .html files |
| Intelligence layer disabled | Set OPENAI_API_KEY; intelligence gracefully degrades without it |
| HTTP API CORS errors | Check CORS middleware is enabled in server_http.py for your domain |
| Time filter not working | Check time_filters.py supports your date format; try simpler queries like "last week" |
