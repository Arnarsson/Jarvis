# Deep Conversation Memory Pipeline

This module provides deep indexing of AI conversations with semantic chunking, automatic tagging, and rich metadata extraction.

## Problem
- 5,040 conversations (3,802 ChatGPT + 1,238 Claude)
- Average 27k chars each = 134.8 MB total
- Previously: ONE vector per conversation → all detail lost

## Solution
- **Chunking**: Split into ~500 token chunks with overlap
- **Tagging**: Extract people, projects, decisions, action items, topics, dates, sentiment
- **Indexing**: Store in Qdrant with full metadata for rich filtering
- **Search**: Enhanced semantic search + timeline browsing

## Architecture

### 1. Chunker (`chunker.py`)
Splits conversations into ~2000 char chunks (~500 tokens) with 200 char overlap.
- Preserves message boundaries (splits on "Human:", "Assistant:", etc.)
- Each chunk maintains conversation metadata

### 2. Tagger (`tagger.py`)
Extracts metadata using regex/heuristics (NO LLM calls):
- **people**: Names near 'with', 'from', '@', capitalized words
- **projects**: Words after 'project', 'repo', GitHub URLs, repeated proper nouns
- **decisions**: Sentences with 'decided', 'agreed', 'will do', etc.
- **action_items**: Sentences with 'need to', 'should', 'TODO', etc.
- **topics**: Top 5 keywords (TF-IDF style, skip stopwords)
- **dates_mentioned**: Date patterns (YYYY-MM-DD, Month Day Year, etc.)
- **sentiment**: Positive/negative/neutral based on keywords

### 3. Indexer (`indexer.py`)
Creates `memory_chunks` Qdrant collection and indexes all conversations.
- Dense vectors: 384-dim (bge-small-en-v1.5)
- Sparse vectors: SPLADE for keyword matching
- Hybrid search with RRF fusion
- Batch processing (100 conversations at a time)

### 4. API (`memory_timeline.py`)
REST endpoints for querying memory:
- `GET /api/v2/memory/timeline` - Chronological timeline with filters
- `GET /api/v2/memory/search` - Enhanced semantic search
- `GET /api/v2/memory/stats` - Collection statistics

## Usage

### Running the Indexer

Inside the Docker container:

```bash
# Run the full pipeline (chunk + tag + index)
docker exec -it jarvis-server python -m jarvis_server.memory.indexer
```

This will:
1. Create the `memory_chunks` collection in Qdrant
2. Process all conversations from PostgreSQL in batches
3. Chunk each conversation
4. Extract tags from each chunk
5. Generate embeddings
6. Index into Qdrant

Progress is logged:
```
Processing batch 1/51 (conversations: 100)
Processing batch 2/51 (conversations: 100)
...
Indexing pipeline complete!
Collection stats: 45,234 chunks indexed
```

### API Examples

**Search for decisions:**
```bash
curl "http://localhost:8000/api/v2/memory/search?q=authentication&tags=decisions&limit=10"
```

**Get timeline of action items:**
```bash
curl "http://localhost:8000/api/v2/memory/timeline?filter=actions&start=2026-01-01&limit=50"
```

**Search by person:**
```bash
curl "http://localhost:8000/api/v2/memory/search?q=project+planning&tags=John,Sarah&sentiment=positive"
```

**Get stats:**
```bash
curl "http://localhost:8000/api/v2/memory/stats"
```

## Database Schema

**Source:** PostgreSQL table `conversations`
```sql
CREATE TABLE conversations (
    id VARCHAR(36) PRIMARY KEY,
    external_id VARCHAR(100),
    source VARCHAR(20),  -- chatgpt, claude, grok
    title VARCHAR(500),
    full_text TEXT,
    message_count INTEGER,
    conversation_date TIMESTAMP WITH TIME ZONE,
    imported_at TIMESTAMP WITH TIME ZONE,
    processing_status VARCHAR(20)
);
```

**Target:** Qdrant collection `memory_chunks`
- Vector: 384-dim dense + sparse
- Payload:
  - conversation_id, source, title, chunk_text
  - chunk_index, total_chunks, conversation_date
  - people[], projects[], decisions[], action_items[]
  - topics[], dates_mentioned[], sentiment

## Performance

- **Chunking**: ~100 conversations/sec
- **Tagging**: ~50 chunks/sec (pure regex, no LLM)
- **Embedding**: ~20 chunks/sec (bge-small-en-v1.5)
- **Indexing**: Batch upsert of 100 chunks at once

**Total time for 5,040 conversations:**
- Estimated: 50,000 chunks
- Processing: ~45 minutes (with batching)

## Future Improvements

1. **Incremental updates**: Only process new/changed conversations
2. **Entity linking**: Resolve "John" across conversations
3. **Relationship extraction**: Who works on which projects
4. **Temporal queries**: "What was decided about X last month?"
5. **Cross-reference**: Link decisions to action items
6. **Smart summaries**: Per-conversation rollups

## Troubleshooting

**Collection not found:**
```bash
# Recreate the collection
docker exec -it jarvis-server python -c "
from jarvis_server.memory.indexer import create_memory_collection
import asyncio
asyncio.run(create_memory_collection())
"
```

**Slow indexing:**
- Increase BATCH_SIZE in indexer.py (default: 100)
- Check Qdrant disk space
- Monitor Docker container resources

**Missing tags:**
- Review tagger.py patterns
- Add custom keywords to POSITIVE_WORDS, NEGATIVE_WORDS
- Adjust regex patterns for your domain
