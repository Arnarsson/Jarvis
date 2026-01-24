"""OCR processor using EasyOCR for screenshot text extraction."""

import logging
from functools import lru_cache

import easyocr
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class OCRProcessor:
    """EasyOCR wrapper for screenshot text extraction."""

    def __init__(self, gpu: bool = True, languages: list[str] | None = None):
        self.languages = languages or ["en"]
        self.gpu = gpu
        self._reader: easyocr.Reader | None = None

    @property
    def reader(self) -> easyocr.Reader:
        """Lazy initialization of EasyOCR reader (5-10s startup)."""
        if self._reader is None:
            logger.info(f"Initializing EasyOCR reader (gpu={self.gpu})")
            self._reader = easyocr.Reader(
                self.languages,
                gpu=self.gpu,
            )
        return self._reader

    def preprocess(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for better OCR accuracy."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if too large
        max_dim = 2000
        if max(image.size) > max_dim:
            ratio = max_dim / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        return np.array(image)

    def extract_text(self, filepath: str) -> str:
        """Extract text from image file."""
        image = Image.open(filepath)
        img_array = self.preprocess(image)

        results = self.reader.readtext(
            img_array,
            detail=0,  # Return just text, not bounding boxes
            paragraph=True,  # Group into paragraphs
        )

        return "\n".join(results)


@lru_cache(maxsize=1)
def get_ocr_processor() -> OCRProcessor:
    """Get singleton OCR processor instance."""
    return OCRProcessor(gpu=True)
