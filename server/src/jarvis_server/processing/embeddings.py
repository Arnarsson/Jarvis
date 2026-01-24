"""Embedding processor using FastEmbed for dense and sparse vectors."""

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from fastembed import SparseTextEmbedding, TextEmbedding

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    dense: np.ndarray  # 384-dim dense vector
    sparse_indices: list[int]
    sparse_values: list[float]


class EmbeddingProcessor:
    """FastEmbed wrapper for dense + sparse embeddings."""

    # Model names (constant for hybrid search compatibility)
    DENSE_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions
    SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or "/data/models/fastembed"
        self._dense_model: TextEmbedding | None = None
        self._sparse_model: SparseTextEmbedding | None = None

    @property
    def dense_model(self) -> TextEmbedding:
        """Lazy initialization of dense embedding model."""
        if self._dense_model is None:
            logger.info(f"Loading dense model: {self.DENSE_MODEL}")
            self._dense_model = TextEmbedding(
                model_name=self.DENSE_MODEL,
                cache_dir=self.cache_dir,
            )
        return self._dense_model

    @property
    def sparse_model(self) -> SparseTextEmbedding:
        """Lazy initialization of sparse embedding model."""
        if self._sparse_model is None:
            logger.info(f"Loading sparse model: {self.SPARSE_MODEL}")
            self._sparse_model = SparseTextEmbedding(
                model_name=self.SPARSE_MODEL,
                cache_dir=self.cache_dir,
            )
        return self._sparse_model

    def embed(self, text: str) -> EmbeddingResult:
        """Generate both dense and sparse embeddings for text."""
        # Dense embedding (384-dim)
        dense_list = list(self.dense_model.embed([text]))
        dense_vec = dense_list[0]

        # Sparse embedding (SPLADE)
        sparse_list = list(self.sparse_model.embed([text]))
        sparse_vec = sparse_list[0]

        return EmbeddingResult(
            dense=dense_vec,
            sparse_indices=sparse_vec.indices.tolist(),
            sparse_values=sparse_vec.values.tolist(),
        )

    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        dense_vecs = list(self.dense_model.embed(texts))
        sparse_vecs = list(self.sparse_model.embed(texts))

        return [
            EmbeddingResult(
                dense=dense,
                sparse_indices=sparse.indices.tolist(),
                sparse_values=sparse.values.tolist(),
            )
            for dense, sparse in zip(dense_vecs, sparse_vecs)
        ]


@lru_cache(maxsize=1)
def get_embedding_processor() -> EmbeddingProcessor:
    """Get singleton embedding processor instance."""
    return EmbeddingProcessor()
