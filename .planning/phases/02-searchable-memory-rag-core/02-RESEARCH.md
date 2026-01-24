# Phase 2: Searchable Memory (RAG Core) - Research

**Researched:** 2026-01-24
**Domain:** RAG pipeline (OCR + embeddings + hybrid search) with FastAPI background processing
**Confidence:** HIGH

## Summary

This phase implements the core RAG (Retrieval-Augmented Generation) pipeline for making captured screenshots searchable via natural language queries. The system processes screenshots with OCR to extract text, generates embeddings for semantic search, and stores vectors in Qdrant for hybrid retrieval combining semantic understanding, keyword matching, and temporal filtering.

The standard approach uses:
- **OCR**: EasyOCR for server-side text extraction (GPU-accelerated, handles varied screenshot quality)
- **Embeddings**: FastEmbed with `BAAI/bge-small-en-v1.5` (384-dim dense) + `prithivida/Splade_PP_en_v1` (sparse) for hybrid search
- **Vector Storage**: Qdrant with both dense and sparse vector configs, payload indices for timestamp filtering
- **Background Processing**: ARQ (Async Redis Queue) for non-blocking pipeline execution
- **Chat Import**: JSON parsing for ChatGPT/Claude/Grok conversation formats

**Primary recommendation:** Use FastEmbed + Qdrant's hybrid search with RRF fusion. Process OCR with EasyOCR on server (GPU if available), using ARQ workers to handle backlog without blocking new captures.

## Standard Stack

The established libraries/tools for this domain:

### Core - OCR & Embeddings

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| easyocr | 1.7.x | Text extraction from screenshots | 80+ languages, GPU support, handles noisy images well |
| fastembed | 0.4.x | Dense + sparse embeddings | Qdrant-native, ONNX runtime, lightweight, no PyTorch bloat |
| qdrant-client | 1.12.x | Vector database client | Already deployed, supports hybrid search natively |

### Core - Background Processing

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arq | 0.26.x | Async task queue | Built for asyncio/FastAPI, Redis-backed, job retries |
| redis | 5.x | Queue backend | Already common infra, ARQ's native backend |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pillow | 10.x | Image preprocessing | Resize before OCR, format conversion |
| orjson | 3.x | Fast JSON parsing | Chat export import (large files) |
| python-dateutil | 2.x | Date parsing | Chat export timestamp normalization |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| EasyOCR | Tesseract | Tesseract faster on CPU, but struggles with messy layouts |
| EasyOCR | docTR | docTR better for documents, EasyOCR better for screenshots |
| FastEmbed | sentence-transformers | sentence-transformers more flexible but heavier (PyTorch) |
| ARQ | Celery | Celery more features but sync-first design, harder with async |
| ARQ | FastAPI BackgroundTasks | No job tracking, results lost on crash |

**Installation (Server additions):**
```bash
pip install easyocr fastembed arq redis orjson python-dateutil
# GPU support: pip install torch torchvision (EasyOCR will use GPU automatically)
```

## Architecture Patterns

### Recommended Project Structure Addition

```
server/src/jarvis_server/
├── processing/
│   ├── __init__.py
│   ├── ocr.py            # EasyOCR wrapper, preprocessing
│   ├── embeddings.py     # FastEmbed wrapper (dense + sparse)
│   ├── pipeline.py       # Orchestrates OCR -> embed -> store
│   └── tasks.py          # ARQ task definitions
├── search/
│   ├── __init__.py
│   ├── hybrid.py         # Qdrant hybrid search implementation
│   ├── schemas.py        # Search request/response models
│   └── api.py            # Search API endpoints
├── imports/
│   ├── __init__.py
│   ├── chatgpt.py        # ChatGPT conversation parser
│   ├── claude.py         # Claude conversation parser
│   ├── grok.py           # Grok conversation parser
│   └── api.py            # Import API endpoints
└── vector/
    ├── __init__.py
    └── qdrant.py         # Qdrant client wrapper (hybrid config)
```

### Pattern 1: Hybrid Search with Qdrant

**What:** Combine dense (semantic) + sparse (keyword) vectors with RRF fusion
**When to use:** All search queries - provides both semantic understanding and exact keyword matching

```python
# Source: Qdrant documentation + FastEmbed examples
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding

# Initialize embedding models
dense_model = TextEmbedding("BAAI/bge-small-en-v1.5")
sparse_model = SparseTextEmbedding("prithivida/Splade_PP_en_v1")

# Collection setup with both vector types
client.create_collection(
    collection_name="captures",
    vectors_config={
        "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams()
    },
)

# Create timestamp index for temporal filtering
client.create_payload_index(
    collection_name="captures",
    field_name="timestamp",
    field_schema=models.PayloadSchemaType.DATETIME,
)

# Hybrid search with RRF fusion
def search(query: str, time_filter: dict | None = None) -> list:
    # Generate embeddings
    dense_vec = list(dense_model.embed([query]))[0]
    sparse_vec = list(sparse_model.embed([query]))[0]

    # Build filter if time constraints provided
    filter_condition = None
    if time_filter:
        filter_condition = models.Filter(
            must=[
                models.FieldCondition(
                    key="timestamp",
                    range=models.DatetimeRange(
                        gte=time_filter.get("gte"),
                        lte=time_filter.get("lte"),
                    )
                )
            ]
        )

    # Execute hybrid search
    results = client.query_points(
        collection_name="captures",
        prefetch=[
            models.Prefetch(
                query=dense_vec.tolist(),
                using="dense",
                limit=50,
                filter=filter_condition,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="sparse",
                limit=50,
                filter=filter_condition,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=10,
        with_payload=True,
    )
    return results.points
```

### Pattern 2: ARQ Background Processing Pipeline

**What:** Non-blocking OCR and embedding processing
**When to use:** Processing new captures without blocking the upload endpoint

```python
# Source: ARQ documentation
from arq import create_pool, cron
from arq.connections import RedisSettings

# tasks.py
async def process_capture(ctx: dict, capture_id: str) -> dict:
    """Process a single capture: OCR -> embed -> store in Qdrant."""
    db = ctx["db"]
    ocr = ctx["ocr"]
    embedder = ctx["embedder"]
    qdrant = ctx["qdrant"]

    # 1. Load capture from database
    capture = await db.get_capture(capture_id)
    if not capture:
        return {"status": "not_found", "id": capture_id}

    # 2. Run OCR
    text = await ocr.extract_text(capture.filepath)

    # 3. Update database with OCR text
    await db.update_capture_ocr(capture_id, text)

    # 4. Generate embeddings (skip if no text)
    if text.strip():
        dense_vec, sparse_vec = await embedder.embed(text)

        # 5. Store in Qdrant
        await qdrant.upsert_capture(
            capture_id=capture_id,
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            payload={
                "timestamp": capture.timestamp.isoformat(),
                "filepath": capture.filepath,
                "text_preview": text[:200],
            }
        )

    return {"status": "processed", "id": capture_id, "text_length": len(text)}

async def process_backlog(ctx: dict) -> dict:
    """Process unprocessed captures (cron job)."""
    db = ctx["db"]
    redis = ctx["redis"]

    # Find captures without embeddings
    pending = await db.get_unprocessed_captures(limit=100)

    for capture in pending:
        await redis.enqueue_job("process_capture", capture.id)

    return {"queued": len(pending)}

# Worker settings
class WorkerSettings:
    functions = [process_capture, process_backlog]
    cron_jobs = [
        cron(process_backlog, hour={0, 6, 12, 18}, minute=0)  # Every 6 hours
    ]
    max_jobs = 5  # Limit concurrent OCR jobs (memory intensive)
    job_timeout = 300  # 5 minutes per capture
    redis_settings = RedisSettings()

    @staticmethod
    async def on_startup(ctx: dict):
        """Initialize shared resources."""
        ctx["ocr"] = OCRProcessor(gpu=True)
        ctx["embedder"] = EmbeddingProcessor()
        ctx["qdrant"] = QdrantWrapper()
        ctx["db"] = await get_async_db()
```

### Pattern 3: OCR Preprocessing for Screenshots

**What:** Optimize screenshots before OCR for better accuracy
**When to use:** All screenshot processing

```python
# Source: EasyOCR documentation + community best practices
import easyocr
from PIL import Image
import numpy as np

class OCRProcessor:
    def __init__(self, gpu: bool = True, languages: list = None):
        self.languages = languages or ["en"]
        self.reader = easyocr.Reader(
            self.languages,
            gpu=gpu,
            model_storage_directory="/data/models/easyocr",
        )

    def preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for better OCR accuracy."""
        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if too large (EasyOCR handles this, but explicit is better)
        max_dim = 2000
        if max(image.size) > max_dim:
            ratio = max_dim / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        return np.array(image)

    async def extract_text(self, filepath: str) -> str:
        """Extract text from screenshot."""
        image = Image.open(filepath)
        img_array = self.preprocess(image)

        # Run OCR (detail=0 returns just text)
        results = self.reader.readtext(
            img_array,
            detail=0,
            paragraph=True,  # Group into paragraphs
        )

        return "\n".join(results)
```

### Pattern 4: Chat Export Parsing (ChatGPT)

**What:** Parse ChatGPT conversations.json export format
**When to use:** Importing user's ChatGPT history

```python
# Source: Community research on ChatGPT export format
import orjson
from datetime import datetime
from typing import Iterator

def parse_chatgpt_export(filepath: str) -> Iterator[dict]:
    """Parse ChatGPT conversations.json export file.

    Yields conversation dicts with:
    - id: conversation UUID
    - title: conversation title
    - messages: list of {role, content, timestamp}
    """
    with open(filepath, "rb") as f:
        data = orjson.loads(f.read())

    for conv in data:
        conv_id = conv.get("id")
        title = conv.get("title", "Untitled")
        mapping = conv.get("mapping", {})

        messages = []
        for node_id, node in mapping.items():
            message = node.get("message")
            if not message:
                continue

            author = message.get("author", {})
            role = author.get("role")  # "user", "assistant", "system"

            content = message.get("content", {})
            content_type = content.get("content_type")
            parts = content.get("parts", [])

            if content_type == "text" and parts:
                text = parts[0] if isinstance(parts[0], str) else ""
                if text.strip():
                    timestamp = message.get("create_time")
                    messages.append({
                        "role": role,
                        "content": text,
                        "timestamp": datetime.fromtimestamp(timestamp) if timestamp else None,
                    })

        # Sort by timestamp
        messages.sort(key=lambda m: m["timestamp"] or datetime.min)

        yield {
            "id": conv_id,
            "title": title,
            "messages": messages,
            "source": "chatgpt",
        }
```

### Pattern 5: Text Chunking for Embeddings

**What:** Split OCR text into chunks suitable for embedding
**When to use:** When OCR text exceeds embedding model context

```python
# Source: RAG best practices research
from typing import Iterator

def chunk_text(
    text: str,
    chunk_size: int = 400,  # tokens ~= chars / 4
    overlap: int = 50,
) -> Iterator[str]:
    """Split text into overlapping chunks.

    Uses simple character-based splitting with paragraph awareness.
    """
    # For screenshots, OCR text is usually short
    # Skip chunking if under threshold
    if len(text) < chunk_size * 4:  # ~1 embedding worth
        yield text
        return

    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        # If adding paragraph exceeds limit, yield current and start new
        if len(current_chunk) + len(para) > chunk_size * 4:
            if current_chunk:
                yield current_chunk.strip()
            current_chunk = para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    # Yield remaining
    if current_chunk.strip():
        yield current_chunk.strip()
```

### Anti-Patterns to Avoid

- **Processing OCR in upload endpoint:** Blocks response, loses work on crash. Use background jobs.
- **Single vector type:** Dense-only misses exact keywords; sparse-only misses semantic similarity.
- **No payload index on timestamp:** Makes time-filtered queries extremely slow at scale.
- **Loading EasyOCR per request:** Model loading takes 5-10s. Initialize once in worker startup.
- **Storing full text in Qdrant payload:** Bloats vector DB. Store preview, full text in PostgreSQL.
- **Processing all captures immediately:** Can overwhelm system. Use queue with rate limiting.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text embeddings | Custom Word2Vec | FastEmbed/sentence-transformers | MTEB-benchmarked models, optimized inference |
| Sparse vectors | Custom TF-IDF | SPLADE via FastEmbed | Learned sparse representations outperform TF-IDF |
| Search fusion | Manual score normalization | Qdrant RRF fusion | Battle-tested, handles score distribution differences |
| OCR preprocessing | Custom image filters | EasyOCR built-in | Handles DPI, orientation, noise automatically |
| Job queue | Threading + database polling | ARQ | Reliable delivery, retries, monitoring |
| Chat export parsing | Regex extraction | Proper JSON parsing with orjson | Edge cases in message content, nested structures |

**Key insight:** Hybrid search requires careful score fusion between dense and sparse results. Qdrant's built-in RRF and DBSF fusion methods handle the statistical complexity of combining different scoring distributions.

## Common Pitfalls

### Pitfall 1: EasyOCR GPU Memory Exhaustion

**What goes wrong:** CUDA out of memory errors after processing several images
**Why it happens:** EasyOCR doesn't fully release GPU memory between calls; memory accumulates
**How to avoid:** Limit concurrent OCR jobs (max_jobs=5); consider CPU mode for reliability; restart workers periodically
**Warning signs:** Increasing memory usage over time, errors after ~15-20 images

### Pitfall 2: Embedding Dimension Mismatch

**What goes wrong:** Qdrant rejects vectors on upsert
**Why it happens:** Collection created with wrong vector size, or model changed
**How to avoid:** Always use model's actual output dimension; verify before collection creation
**Warning signs:** "Vector dimension mismatch" errors

### Pitfall 3: Timestamp Index Not Created

**What goes wrong:** Time-filtered searches take 10+ seconds
**Why it happens:** Qdrant scans all points without datetime payload index
**How to avoid:** Create payload index on timestamp field immediately after collection creation
**Warning signs:** Time filters much slower than unfiltered queries

### Pitfall 4: Chat Export Memory Blowup

**What goes wrong:** OOM when importing large ChatGPT export
**Why it happens:** Loading entire JSON into memory (can be 100MB+)
**How to avoid:** Stream-parse with ijson or process conversations one at a time with orjson
**Warning signs:** Memory spike during import, slow/failed imports

### Pitfall 5: Empty OCR Text Handling

**What goes wrong:** Empty vectors stored, search returns meaningless results
**Why it happens:** Images with no text (logos, photos) produce empty OCR output
**How to avoid:** Skip embedding for empty/whitespace-only text; mark capture as "no-text" in metadata
**Warning signs:** Search results include irrelevant captures

### Pitfall 6: ARQ Job Loss on Worker Crash

**What goes wrong:** Captures never get processed, stuck in "processing" state
**Why it happens:** Worker dies mid-job, database marked as processing but Qdrant never updated
**How to avoid:** Use ARQ's job_timeout; add reconciliation cron job to requeue stale jobs
**Warning signs:** Growing backlog of "processing" captures that never complete

## Code Examples

### Complete Qdrant Collection Setup

```python
# Source: Qdrant documentation
from qdrant_client import QdrantClient, models

def setup_captures_collection(client: QdrantClient):
    """Create Qdrant collection optimized for hybrid search."""
    collection_name = "captures"

    # Check if exists
    collections = client.get_collections().collections
    if any(c.name == collection_name for c in collections):
        return

    # Create with both vector types
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(
                size=384,  # bge-small-en-v1.5
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(
                    on_disk=False,  # Keep in memory for speed
                )
            )
        },
    )

    # Create payload indices for filtering
    client.create_payload_index(
        collection_name=collection_name,
        field_name="timestamp",
        field_schema=models.PayloadSchemaType.DATETIME,
    )

    client.create_payload_index(
        collection_name=collection_name,
        field_name="source",  # "screen", "chatgpt", "claude", etc.
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
```

### Embedding Generation with FastEmbed

```python
# Source: FastEmbed documentation
from fastembed import TextEmbedding, SparseTextEmbedding
from dataclasses import dataclass
import numpy as np

@dataclass
class EmbeddingResult:
    dense: np.ndarray
    sparse_indices: list[int]
    sparse_values: list[float]

class EmbeddingProcessor:
    def __init__(self):
        # Dense model: 384 dimensions, fast, good quality
        self.dense_model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            cache_dir="/data/models/fastembed",
        )
        # Sparse model: SPLADE for keyword matching
        self.sparse_model = SparseTextEmbedding(
            model_name="prithivida/Splade_PP_en_v1",
            cache_dir="/data/models/fastembed",
        )

    def embed(self, text: str) -> EmbeddingResult:
        """Generate both dense and sparse embeddings."""
        # Dense embedding
        dense_list = list(self.dense_model.embed([text]))
        dense_vec = dense_list[0]

        # Sparse embedding
        sparse_list = list(self.sparse_model.embed([text]))
        sparse_vec = sparse_list[0]

        return EmbeddingResult(
            dense=dense_vec,
            sparse_indices=sparse_vec.indices.tolist(),
            sparse_values=sparse_vec.values.tolist(),
        )
```

### Search API Endpoint

```python
# Source: FastAPI + Qdrant documentation
from fastapi import APIRouter, Query
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    sources: Optional[list[str]] = None  # ["screen", "chatgpt", "claude"]

class SearchResult(BaseModel):
    capture_id: str
    score: float
    text_preview: str
    timestamp: datetime
    source: str

@router.post("/", response_model=list[SearchResult])
async def search_memories(request: SearchRequest):
    """Search captured memories using natural language."""
    # Build filter conditions
    filters = []

    if request.start_date or request.end_date:
        filters.append(
            models.FieldCondition(
                key="timestamp",
                range=models.DatetimeRange(
                    gte=request.start_date,
                    lte=request.end_date,
                ),
            )
        )

    if request.sources:
        filters.append(
            models.FieldCondition(
                key="source",
                match=models.MatchAny(any=request.sources),
            )
        )

    filter_condition = models.Filter(must=filters) if filters else None

    # Generate query embeddings
    embedder = get_embedder()
    embedding = embedder.embed(request.query)

    # Execute hybrid search
    results = qdrant_client.query_points(
        collection_name="captures",
        prefetch=[
            models.Prefetch(
                query=embedding.dense.tolist(),
                using="dense",
                limit=50,
                filter=filter_condition,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=embedding.sparse_indices,
                    values=embedding.sparse_values,
                ),
                using="sparse",
                limit=50,
                filter=filter_condition,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=request.limit,
        with_payload=True,
    )

    return [
        SearchResult(
            capture_id=str(point.id),
            score=point.score,
            text_preview=point.payload.get("text_preview", ""),
            timestamp=point.payload.get("timestamp"),
            source=point.payload.get("source", "screen"),
        )
        for point in results.points
    ]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Dense-only search | Hybrid (dense + sparse) | 2023+ | Better recall for exact terms + semantic understanding |
| Tesseract CPU | EasyOCR GPU | 2021+ | 5-10x faster, better accuracy on noisy images |
| sentence-transformers | FastEmbed | 2024+ | Lighter weight, ONNX runtime, similar quality |
| Celery | ARQ | 2023+ | Native asyncio, better FastAPI fit |
| Manual RRF implementation | Qdrant Query API | Qdrant 1.10+ | Server-side fusion, simpler client code |

**Deprecated/outdated:**
- **pgvector for hybrid search**: Lacks native sparse vector support; requires manual BM25
- **TF-IDF sparse vectors**: SPLADE learned vectors significantly outperform
- **Full-text search only**: Misses semantic similarity entirely

## Open Questions

Things that couldn't be fully resolved:

1. **Optimal chunk size for screenshot OCR text**
   - What we know: Screenshots typically have 100-500 words; standard RAG recommends 400 tokens
   - What's unclear: Whether screenshots need chunking at all given typical text length
   - Recommendation: Start without chunking (single embedding per capture), add if needed

2. **Claude export format specifics**
   - What we know: Claude exports as ZIP with JSON in .dms format, requires parsing
   - What's unclear: Exact JSON schema (varies by export type/time)
   - Recommendation: Build parser iteratively based on actual export samples

3. **Grok export format**
   - What we know: Available via accounts.x.ai, various third-party tools exist
   - What's unclear: Official JSON structure, whether format is stable
   - Recommendation: Support via third-party exporter tools (de:dobe, YourAIScroll)

4. **Timeline browsing implementation**
   - What we know: Need to show visual history with thumbnails by date
   - What's unclear: Frontend framework choice, pagination strategy for large histories
   - Recommendation: Defer frontend decisions; API should support cursor-based pagination by timestamp

## Sources

### Primary (HIGH confidence)
- [Qdrant Hybrid Search Documentation](https://qdrant.tech/documentation/concepts/hybrid-queries/) - Query API, prefetch, fusion
- [FastEmbed Documentation](https://qdrant.tech/documentation/fastembed/) - Model list, sparse embeddings
- [Qdrant Payload Indexing](https://qdrant.tech/documentation/concepts/indexing/) - Timestamp index configuration
- [ARQ Documentation](https://arq-docs.helpmanual.io/) - Task queue patterns, retries, cron
- [EasyOCR GitHub](https://github.com/JaidedAI/EasyOCR) - GPU usage, languages, API

### Secondary (MEDIUM confidence)
- [FastEmbed Hybrid Search Tutorial](https://qdrant.tech/documentation/beginner-tutorials/hybrid-search-fastembed/) - End-to-end example
- [Qdrant Filtering Guide](https://qdrant.tech/articles/vector-search-filtering/) - Payload index performance
- [RAG Chunking Best Practices](https://weaviate.io/blog/chunking-strategies-for-rag) - Chunk size recommendations
- [FastAPI Background Tasks vs ARQ](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/) - Task queue comparison

### Tertiary (LOW confidence)
- ChatGPT export format - Community reverse-engineering, format may change
- EasyOCR GPU memory issues - GitHub issues, anecdotal reports
- Grok export format - Third-party tools, not official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries have official documentation, production-proven
- Architecture patterns: HIGH - Based on official examples and documentation
- Pitfalls: MEDIUM - Mix of official docs and community reports

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - Qdrant/FastEmbed APIs stable)
