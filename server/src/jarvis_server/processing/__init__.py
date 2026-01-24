"""Processing modules for OCR and embeddings."""

from .embeddings import EmbeddingProcessor, EmbeddingResult
from .ocr import OCRProcessor

__all__ = ["OCRProcessor", "EmbeddingProcessor", "EmbeddingResult"]
