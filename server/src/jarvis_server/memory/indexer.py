"""Conversation indexer - creates memory_chunks collection and indexes conversations.

Run with: python -m jarvis_server.memory.indexer
"""

import asyncio
import logging
import sys
from datetime import datetime
from uuid import uuid5, NAMESPACE_DNS

import structlog
from qdrant_client import models
from sqlalchemy import select, func

from jarvis_server.config import get_settings
from jarvis_server.db.models import ConversationRecord
from jarvis_server.db.session import AsyncSessionLocal as async_session_maker
from jarvis_server.memory.chunker import chunk_conversation
from jarvis_server.memory.tagger import extract_tags
from jarvis_server.processing.embeddings import get_embedding_processor
from jarvis_server.vector.qdrant import get_qdrant

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = structlog.get_logger(__name__)

COLLECTION_NAME = "memory_chunks"
BATCH_SIZE = 100


async def create_memory_collection():
    """Create memory_chunks collection in Qdrant."""
    qdrant = get_qdrant()
    
    # Check if collection already exists
    collections = qdrant.client.get_collections().collections
    if any(c.name == COLLECTION_NAME for c in collections):
        logger.info(f"Collection {COLLECTION_NAME} already exists")
        return
    
    logger.info(f"Creating collection {COLLECTION_NAME}")
    
    # Create collection with same config as captures (384-dim dense + sparse)
    qdrant.client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(on_disk=False)
            )
        },
    )
    
    # Create payload indices for filtering
    qdrant.client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="conversation_date",
        field_schema=models.PayloadSchemaType.DATETIME,
    )
    qdrant.client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="source",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    qdrant.client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="sentiment",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    
    logger.info(f"Collection {COLLECTION_NAME} created successfully")


async def get_conversation_count() -> int:
    """Get total conversation count from database."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.count()).select_from(ConversationRecord)
        )
        return result.scalar() or 0


async def process_conversations_batch(
    conversations: list[ConversationRecord],
    batch_num: int,
    total_batches: int
):
    """Process a batch of conversations: chunk, tag, embed, and index.
    
    Args:
        conversations: List of ConversationRecord objects
        batch_num: Current batch number (1-indexed)
        total_batches: Total number of batches
    """
    qdrant = get_qdrant()
    embedder = get_embedding_processor()
    
    all_points = []
    chunks_processed = 0
    
    for conv in conversations:
        try:
            # 1. Chunk the conversation
            conversation_date_iso = None
            if conv.conversation_date:
                conversation_date_iso = conv.conversation_date.isoformat()
            
            chunks = chunk_conversation(
                conversation_id=conv.id,
                source=conv.source,
                title=conv.title,
                full_text=conv.full_text,
                conversation_date=conversation_date_iso
            )
            
            # 2. Tag and embed each chunk
            for chunk in chunks:
                # Extract tags
                tags = extract_tags(chunk.chunk_text)
                
                # Generate embeddings
                embedding = embedder.embed(chunk.chunk_text)
                
                # Create point payload
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
                
                # Create point - use uuid5 for deterministic UUID generation
                point_id = str(uuid5(NAMESPACE_DNS, f"{chunk.conversation_id}_{chunk.chunk_index}"))
                point = models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": embedding.dense.tolist(),
                        "sparse": models.SparseVector(
                            indices=embedding.sparse_indices,
                            values=embedding.sparse_values,
                        ),
                    },
                    payload=payload,
                )
                
                all_points.append(point)
                chunks_processed += 1
        
        except Exception as e:
            logger.error(
                f"Failed to process conversation {conv.id}",
                error=str(e),
                conversation_id=conv.id
            )
            continue
    
    # 3. Batch upsert to Qdrant
    if all_points:
        try:
            qdrant.client.upsert(
                collection_name=COLLECTION_NAME,
                points=all_points,
                wait=True
            )
            logger.info(
                f"Batch {batch_num}/{total_batches} complete",
                conversations=len(conversations),
                chunks=chunks_processed
            )
        except Exception as e:
            logger.error(
                f"Failed to upsert batch {batch_num}",
                error=str(e)
            )


async def index_all_conversations():
    """Index all conversations from database into memory_chunks collection."""
    logger.info("Starting conversation indexing pipeline")
    
    # Get total count
    total_count = await get_conversation_count()
    logger.info(f"Total conversations to process: {total_count}")
    
    if total_count == 0:
        logger.warning("No conversations found in database")
        return
    
    # Process in batches
    total_batches = (total_count + BATCH_SIZE - 1) // BATCH_SIZE
    
    async with async_session_maker() as session:
        for batch_num in range(1, total_batches + 1):
            offset = (batch_num - 1) * BATCH_SIZE
            
            # Fetch batch
            result = await session.execute(
                select(ConversationRecord)
                .order_by(ConversationRecord.conversation_date.desc())
                .offset(offset)
                .limit(BATCH_SIZE)
            )
            conversations = list(result.scalars().all())
            
            if not conversations:
                break
            
            logger.info(
                f"Processing batch {batch_num}/{total_batches}",
                offset=offset,
                count=len(conversations)
            )
            
            # Process batch
            await process_conversations_batch(
                conversations,
                batch_num,
                total_batches
            )
    
    logger.info("Indexing pipeline complete!")


async def get_collection_stats():
    """Get statistics about the memory_chunks collection."""
    qdrant = get_qdrant()
    
    try:
        collection_info = qdrant.client.get_collection(COLLECTION_NAME)
        
        logger.info(
            "Collection stats",
            collection=COLLECTION_NAME,
            vectors_count=collection_info.vectors_count,
            points_count=collection_info.points_count,
        )
        
        return {
            "collection": COLLECTION_NAME,
            "vectors_count": collection_info.vectors_count,
            "points_count": collection_info.points_count,
        }
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return None


async def main():
    """Main entry point for the indexer."""
    logger.info("Memory indexer starting")
    
    # Create collection if needed
    await create_memory_collection()
    
    # Index all conversations
    await index_all_conversations()
    
    # Show stats
    await get_collection_stats()
    
    logger.info("Memory indexer finished")


if __name__ == "__main__":
    # Run the indexer
    asyncio.run(main())
