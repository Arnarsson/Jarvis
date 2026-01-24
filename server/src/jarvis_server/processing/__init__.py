"""Processing modules for OCR and embeddings."""

from .embeddings import EmbeddingProcessor, EmbeddingResult, get_embedding_processor
from .ocr import OCRProcessor, get_ocr_processor
from .pipeline import get_pending_captures, process_single_capture
from .tasks import process_backlog, process_capture

__all__ = [
    "OCRProcessor",
    "get_ocr_processor",
    "EmbeddingProcessor",
    "EmbeddingResult",
    "get_embedding_processor",
    "process_single_capture",
    "get_pending_captures",
    "process_capture",
    "process_backlog",
]
