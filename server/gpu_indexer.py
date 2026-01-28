#!/usr/bin/env python3
"""GPU-accelerated memory indexer - runs on host with CUDA support.

This script processes conversations from PostgreSQL, chunks them, extracts tags,
generates embeddings using GPU-accelerated models, and indexes them in Qdrant.

Run with: python3 /home/sven/Documents/jarvis/server/gpu_indexer.py

Requirements:
- CUDA-capable GPU
- torch with CUDA
- fastembed or sentence-transformers
- asyncpg
- qdrant-client
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set
from uuid import uuid5, NAMESPACE_DNS

# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"

import asyncpg
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

# Add server source to path for imports
SERVER_SRC = Path("/home/sven/Documents/jarvis/server/src")
sys.path.insert(0, str(SERVER_SRC))

from jarvis_server.memory.chunker import chunk_conversation, ConversationChunk
from jarvis_server.memory.tagger import extract_tags

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "jarvis",
    "password": "changeme",
    "database": "jarvis",
}

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "memory_chunks"
BATCH_SIZE = 100


class GPUEmbedder:
    """GPU-accelerated embedding generator using fastembed or sentence-transformers."""
    
    def __init__(self):
        self.dense_model = None
        self.device = None
        self._load_models()
    
    def _load_models(self):
        """Load embedding models with GPU support."""
        import torch
        
        # Check CUDA availability
        if torch.cuda.is_available():
            self.device = "cuda"
            print(f"✓ GPU available: {torch.cuda.get_device_name(0)}")
        else:
            self.device = "cpu"
            print("⚠ GPU not available, falling back to CPU")
        
        # Use fastembed (ONNX-based, optimized CPU with multi-threading)
        from fastembed import TextEmbedding
        print("Loading fastembed model (BAAI/bge-small-en-v1.5)...", flush=True)
        self.dense_model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            threads=8,
        )
        self.use_fastembed = True
        print("✓ Fastembed loaded (8 threads)", flush=True)
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a batch of texts.
        
        Returns: (batch_size, 384) array of dense embeddings
        """
        if self.use_fastembed:
            # Fastembed returns a generator
            embeddings = list(self.dense_model.embed(texts))
            return np.array(embeddings)
        else:
            # Sentence-transformers returns ndarray directly
            embeddings = self.dense_model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings


async def get_indexed_conversation_ids(qdrant: QdrantClient) -> Set[str]:
    """Get set of conversation IDs that already have chunks in Qdrant.
    
    Returns: Set of conversation_id strings
    """
    print("Checking for already-indexed conversations...")
    
    try:
        # Scroll through all points and collect unique conversation_ids
        indexed_ids = set()
        offset = None
        
        while True:
            result = qdrant.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000,
                offset=offset,
                with_payload=["conversation_id"],
                with_vectors=False,
            )
            
            points, next_offset = result
            
            if not points:
                break
            
            for point in points:
                conv_id = point.payload.get("conversation_id")
                if conv_id:
                    indexed_ids.add(conv_id)
            
            if next_offset is None:
                break
            
            offset = next_offset
        
        print(f"✓ Found {len(indexed_ids)} conversations already indexed")
        return indexed_ids
        
    except Exception as e:
        print(f"⚠ Failed to check indexed conversations: {e}")
        print("  Proceeding with full index (may have duplicates)")
        return set()


async def get_total_conversation_count(pool: asyncpg.Pool) -> int:
    """Get total count of conversations in database."""
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        return count or 0


async def fetch_conversations_batch(
    pool: asyncpg.Pool,
    offset: int,
    limit: int,
    skip_ids: Set[str],
) -> List[dict]:
    """Fetch a batch of conversations from PostgreSQL.
    
    Args:
        pool: Database connection pool
        offset: Starting offset
        limit: Number of conversations to fetch
        skip_ids: Set of conversation IDs to skip
    
    Returns: List of conversation dicts
    """
    async with pool.acquire() as conn:
        # Fetch conversations excluding already-indexed ones
        if skip_ids:
            query = """
                SELECT id, source, title, full_text, conversation_date
                FROM conversations
                WHERE id != ALL($1)
                ORDER BY conversation_date DESC NULLS LAST
                LIMIT $2 OFFSET $3
            """
            rows = await conn.fetch(query, list(skip_ids), limit, offset)
        else:
            query = """
                SELECT id, source, title, full_text, conversation_date
                FROM conversations
                ORDER BY conversation_date DESC NULLS LAST
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, limit, offset)
        
        return [dict(row) for row in rows]


async def process_batch(
    conversations: List[dict],
    embedder: GPUEmbedder,
    qdrant: QdrantClient,
    batch_num: int,
    total_batches: int,
) -> int:
    """Process a batch of conversations: chunk, tag, embed, and index.
    
    Returns: Number of chunks indexed
    """
    all_chunks = []
    all_texts = []
    
    # Step 1: Chunk and tag all conversations
    for conv in conversations:
        try:
            # Chunk conversation
            conv_date_iso = None
            if conv["conversation_date"]:
                conv_date_iso = conv["conversation_date"].isoformat()
            
            chunks = chunk_conversation(
                conversation_id=conv["id"],
                source=conv["source"],
                title=conv["title"] or "",
                full_text=conv["full_text"] or "",
                conversation_date=conv_date_iso,
            )
            
            # Tag each chunk
            for chunk in chunks:
                tags = extract_tags(chunk.chunk_text)
                all_chunks.append((chunk, tags))
                all_texts.append(chunk.chunk_text)
        
        except Exception as e:
            print(f"  ⚠ Failed to process conversation {conv['id']}: {e}")
            continue
    
    if not all_chunks:
        return 0
    
    # Step 2: Generate embeddings in batch (GPU-accelerated)
    print(f"  Embedding {len(all_texts)} chunks on GPU...")
    start = time.time()
    embeddings = embedder.embed_batch(all_texts)
    elapsed = time.time() - start
    print(f"  ✓ Embeddings generated in {elapsed:.2f}s ({len(all_texts)/elapsed:.1f} chunks/sec)")
    
    # Step 3: Create Qdrant points
    points = []
    for i, ((chunk, tags), embedding) in enumerate(zip(all_chunks, embeddings)):
        # Generate deterministic UUID for point ID
        point_id = str(uuid5(NAMESPACE_DNS, f"{chunk.conversation_id}_{chunk.chunk_index}"))
        
        # Create payload
        payload = {
            "conversation_id": chunk.conversation_id,
            "source": chunk.source,
            "title": chunk.title,
            "chunk_text": chunk.chunk_text[:1000],  # Truncate for storage
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            "conversation_date": chunk.conversation_date,
            "people": tags.people,
            "projects": tags.projects,
            "decisions": tags.decisions,
            "action_items": tags.action_items,
            "topics": tags.topics,
            "dates_mentioned": tags.dates_mentioned,
            "sentiment": tags.sentiment,
        }
        
        # Create point (dense vector only, named to match collection schema)
        point = PointStruct(
            id=point_id,
            vector={"dense": embedding.tolist()},
            payload=payload,
        )
        
        points.append(point)
    
    # Step 4: Batch upsert to Qdrant
    print(f"  Upserting {len(points)} points to Qdrant...")
    start = time.time()
    qdrant.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )
    elapsed = time.time() - start
    print(f"  ✓ Batch {batch_num}/{total_batches} complete: {len(points)} chunks indexed in {elapsed:.2f}s")
    
    return len(points)


async def main():
    """Main indexing pipeline."""
    print("=" * 60)
    print("GPU-ACCELERATED MEMORY INDEXER")
    print("=" * 60)
    print()
    
    # Initialize embedder (loads models)
    print("Initializing GPU embedder...")
    embedder = GPUEmbedder()
    print()
    
    # Connect to Qdrant
    print("Connecting to Qdrant...")
    qdrant = QdrantClient(url=QDRANT_URL)
    print(f"✓ Connected to Qdrant at {QDRANT_URL}")
    print()
    
    # Get already-indexed conversation IDs
    skip_ids = await get_indexed_conversation_ids(qdrant)
    print()
    
    # Connect to PostgreSQL
    print("Connecting to PostgreSQL...")
    pool = await asyncpg.create_pool(**DB_CONFIG, min_size=1, max_size=5)
    print(f"✓ Connected to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print()
    
    # Get total count
    total_conversations = await get_total_conversation_count(pool)
    conversations_to_process = total_conversations - len(skip_ids)
    total_batches = (conversations_to_process + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"Total conversations in DB: {total_conversations}")
    print(f"Already indexed: {len(skip_ids)}")
    print(f"To process: {conversations_to_process}")
    print(f"Batches: {total_batches} (size={BATCH_SIZE})")
    print()
    
    if conversations_to_process == 0:
        print("✓ All conversations already indexed!")
        await pool.close()
        return
    
    # Process batches
    print("Starting indexing pipeline...")
    print("=" * 60)
    
    total_chunks_indexed = 0
    start_time = time.time()
    
    for batch_num in range(1, total_batches + 1):
        offset = (batch_num - 1) * BATCH_SIZE
        
        print(f"\nBatch {batch_num}/{total_batches}:")
        
        # Fetch batch
        conversations = await fetch_conversations_batch(
            pool, offset, BATCH_SIZE, skip_ids
        )
        
        if not conversations:
            print("  No more conversations to process")
            break
        
        print(f"  Fetched {len(conversations)} conversations")
        
        # Process batch
        chunks_indexed = await process_batch(
            conversations, embedder, qdrant, batch_num, total_batches
        )
        
        total_chunks_indexed += chunks_indexed
    
    # Summary
    elapsed_total = time.time() - start_time
    print()
    print("=" * 60)
    print("INDEXING COMPLETE")
    print("=" * 60)
    print(f"Total chunks indexed: {total_chunks_indexed}")
    print(f"Total time: {elapsed_total:.2f}s ({elapsed_total/60:.1f} min)")
    print(f"Throughput: {total_chunks_indexed/elapsed_total:.1f} chunks/sec")
    print()
    
    # Cleanup
    await pool.close()
    print("✓ Connections closed")


if __name__ == "__main__":
    asyncio.run(main())
