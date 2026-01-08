# Unified Memory MCP

A unified RAG memory system that ingests ChatGPT + Claude exports into SQLite, creates embeddings with Qdrant, and serves them via an MCP server with hybrid search (lexical FTS5 + semantic vector).

## Architecture

```
ChatGPT Export ─┐
                ├─► chat-export-structurer ─► SQLite ─► indexer.py ─► Qdrant
Claude Export ──┘                              │                        │
                                               └────────────────────────┴─► server.py (MCP)
```

## Features

- **Unified ingestion**: ChatGPT + Claude + Grok exports merged into one SQLite archive
- **Streaming parser**: Handles multi-GB export files with SHA1 dedupe
- **Hybrid retrieval**: Combines FTS5 lexical search (40%) + Qdrant semantic search (60%)
- **MCP-compliant**: Returns OpenAI-expected JSON-in-content-array format
- **Token-aware chunking**: Configurable max/min tokens with message overlap

## Quick Start

### 1. Clone with submodule

```bash
git clone --recurse-submodules https://github.com/YOUR_USERNAME/unified-memory-mcp.git
cd unified-memory-mcp

# If already cloned without submodules:
git submodule update --init --recursive
```

### 2. Start Qdrant

```bash
docker compose up -d
```

### 3. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install ingestion deps
pip install -r vendor/chat-export-structurer/requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your OpenAI API key
```

### 5. Ingest exports

```bash
# ChatGPT export (from Settings > Data controls > Export data)
python vendor/chat-export-structurer/src/ingest.py \
  --in /path/to/chatgpt/conversations.json \
  --db ./memory.sqlite \
  --format chatgpt

# Claude/Anthropic export (from Settings > Export Data)
python vendor/chat-export-structurer/src/ingest.py \
  --in /path/to/claude/conversations.json \
  --db ./memory.sqlite \
  --format anthropic

# Grok export (optional)
python vendor/chat-export-structurer/src/ingest.py \
  --in /path/to/grok/export.json \
  --db ./memory.sqlite \
  --format grok
```

#### Seven-style ingestion & search (optional)

If you prefer the Seven automation flow, a lightweight clone now lives in `seven_tools/`:

```bash
# Import ChatGPT + Claude JSON/ZIP exports (defaults to ./chatgpt-claude exports)
python seven_tools/import_conversations.py --db memory.sqlite

# Run a fast FTS-only search without Qdrant/OpenAI
python seven_tools/search_conversations.py "business plan 2026" --limit 5
python seven_tools/search_conversations.py --stats
python seven_tools/search_conversations.py --view <conversation_id>
```

These scripts automatically add the `conversations` table + FTS triggers to `memory.sqlite`, so the UI and MCP stack can reason over both chunked RAG data and the raw Seven archive.

### 6. Build chunks and embeddings

```bash
export OPENAI_API_KEY="sk-..."

# Create chunks from messages
python indexer.py build-chunks --db ./memory.sqlite

# Embed chunks to Qdrant
python indexer.py embed --db ./memory.sqlite
```

### 7. Start MCP server

```bash
python server.py --db ./memory.sqlite --base-url https://your-domain.example
```

### 8. Explore raw Claude history (optional)

The upstream [claude-history-explorer](https://github.com/adewale/claude-history-explorer) CLI is vendored inside this repo for richer storytelling and regex tooling. Use the new passthrough command to access it without leaving the project:

```bash
memory history projects               # List Claude Code projects
memory history sessions myproject -n 5
memory history search "TODO" -p myproject
memory history show abc123 --raw
memory history wrapped -y 2024 --raw
```

Anything after `memory history` is forwarded directly to the `claude-history` CLI. Use `memory history -- --help` to see the full set of commands (projects, sessions, show, search, export, info, stats, summary, story, wrapped, etc.).

### 9. Launch the web UI

All conversations have already been chunked and indexed, so you can browse them visually:

```bash
uvicorn webapp:app --reload
```

Then open http://127.0.0.1:8000/ to get a lightweight dashboard:

- Hybrid semantic + lexical search with natural-language time filters (`today`, `last 3 weeks`, `December 2024`, etc.)
- Inline result cards displaying snippets and scores
- Per-chunk detail pages with full text and tags
- Claude History Explorer tools (projects, sessions, show) exposed in a terminal-style panel

The web app reuses the same FastAPI stack as the HTTP API, so it respects your `.env` settings for database path and Qdrant configuration.

## MCP Tools

### `search(query: str)`

Returns up to 8 hybrid-ranked results:

```json
{
  "content": [{
    "type": "text",
    "text": "{\"results\": [{\"id\": \"chunk_abc123\", \"title\": \"...\", \"url\": \"...\"}]}"
  }]
}
```

### `fetch(id: str)`

Returns full chunk content:

```json
{
  "content": [{
    "type": "text",
    "text": "{\"id\": \"...\", \"title\": \"...\", \"text\": \"...\", \"url\": \"...\", \"metadata\": {...}}"
  }]
}
```

## Configuration

### Indexer options

| Option | Default | Description |
|--------|---------|-------------|
| `--max-tokens` | 1100 | Maximum tokens per chunk |
| `--min-tokens` | 250 | Minimum tokens (skip smaller chunks) |
| `--overlap-msgs` | 2 | Messages to overlap between chunks |
| `--batch-size` | 64 | Embedding batch size |

### Server options

| Option | Default | Description |
|--------|---------|-------------|
| `--transport` | sse | MCP transport: sse, http, stdio |
| `--host` | 0.0.0.0 | Server bind address |
| `--port` | 8000 | Server port |

### Environment variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings |
| `QDRANT_URL` | Qdrant server URL (default: http://localhost:6333) |
| `QDRANT_COLLECTION` | Collection name (default: memory_chunks) |
| `EMBED_MODEL` | Embedding model (default: text-embedding-3-small) |
| `PUBLIC_BASE_URL` | Base URL for chunk citations |

## Schema Detection

The indexer auto-detects message schemas from `chat-export-structurer`:

- `message_id` / `id`
- `canonical_thread_id` / `thread_id` / `conversation_id`
- `role` / `author_role` / `sender`
- `text` / `content` / `message`
- `ts` / `timestamp` / `created_at`
- `title` / `thread_title` (optional)

## Hybrid Search Algorithm

Retrieval combines:

1. **Lexical (FTS5)**: BM25 scores inverted to 0-1 range
2. **Semantic (Qdrant)**: Cosine similarity scores

Final score: `0.60 * semantic + 0.40 * lexical`

Top-k results are returned, with ties broken by semantic score.
