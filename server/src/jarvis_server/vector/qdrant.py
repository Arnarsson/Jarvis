"""Qdrant client wrapper with hybrid search configuration.

Provides hybrid vector search with:
- Dense vectors: 384-dim from bge-small-en-v1.5
- Sparse vectors: BM25/SPLADE token weights
- Payload indices: timestamp (DATETIME), source (KEYWORD)
"""

from functools import lru_cache

from qdrant_client import QdrantClient, models

from ..config import get_settings


class QdrantWrapper:
    """Wrapper for Qdrant client with hybrid vector configuration."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize Qdrant client.

        Args:
            host: Qdrant server hostname
            port: Qdrant server port
        """
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "captures"

    def setup_captures_collection(self) -> None:
        """Create captures collection with hybrid vector configuration.

        Creates collection with:
        - Dense vectors: 384-dim (bge-small-en-v1.5), cosine distance
        - Sparse vectors: BM25/SPLADE token weights
        - Payload indices: timestamp (DATETIME), source (KEYWORD)

        Skips creation if collection already exists.
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        if any(c.name == self.collection_name for c in collections):
            return

        # Create collection with hybrid vector configuration
        self.client.create_collection(
            collection_name=self.collection_name,
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
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="timestamp",
            field_schema=models.PayloadSchemaType.DATETIME,
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    def upsert_capture(
        self,
        capture_id: str,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        payload: dict,
    ) -> None:
        """Upsert a capture's embeddings into Qdrant.

        Args:
            capture_id: Unique ID for the point (capture UUID)
            dense_vector: 384-dim dense embedding from bge-small-en-v1.5
            sparse_indices: Token indices for sparse vector (BM25/SPLADE)
            sparse_values: Token weights for sparse vector
            payload: Metadata dict with timestamp, filepath, text_preview, source
        """
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=capture_id,
                    vector={
                        "dense": dense_vector,
                        "sparse": models.SparseVector(
                            indices=sparse_indices,
                            values=sparse_values,
                        ),
                    },
                    payload=payload,
                )
            ],
        )


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantWrapper:
    """Get singleton QdrantWrapper instance.

    Returns:
        Cached QdrantWrapper instance configured from settings.
    """
    settings = get_settings()
    return QdrantWrapper(host=settings.qdrant_host, port=settings.qdrant_port)


def setup_captures_collection(wrapper: QdrantWrapper | None = None) -> None:
    """Ensure captures collection exists with proper configuration.

    Args:
        wrapper: Optional QdrantWrapper instance. Uses singleton if not provided.
    """
    if wrapper is None:
        wrapper = get_qdrant()
    wrapper.setup_captures_collection()
