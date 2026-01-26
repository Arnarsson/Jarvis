"""OCR processor for screenshot text extraction.

Uses Tesseract by default (fast on CPU) with EasyOCR fallback for GPU.
"""

import logging
import shutil
from functools import lru_cache

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)


class OCRProcessor:
    """OCR processor with Tesseract (fast CPU) and EasyOCR (GPU) support."""

    def __init__(
        self,
        use_gpu: bool = False,
        languages: list[str] | None = None,
        prefer_tesseract: bool = True,
    ):
        self.languages = languages or ["eng", "dan"]
        self.use_gpu = use_gpu
        self.prefer_tesseract = prefer_tesseract
        self._tesseract_available: bool | None = None
        self._easyocr_reader = None

    @property
    def tesseract_available(self) -> bool:
        """Check if Tesseract is installed."""
        if self._tesseract_available is None:
            self._tesseract_available = shutil.which("tesseract") is not None
            if self._tesseract_available:
                logger.info("Tesseract OCR available")
            else:
                logger.info("Tesseract not found, will use EasyOCR")
        return self._tesseract_available

    @property
    def easyocr_reader(self):
        """Lazy initialization of EasyOCR reader."""
        if self._easyocr_reader is None:
            import easyocr

            # Convert language codes for EasyOCR (uses different format)
            easyocr_langs = []
            for lang in self.languages:
                if lang in ("eng", "en"):
                    easyocr_langs.append("en")
                elif lang in ("dan", "da"):
                    easyocr_langs.append("da")
                else:
                    easyocr_langs.append(lang)

            logger.info(f"Initializing EasyOCR (gpu={self.use_gpu}, langs={easyocr_langs})")
            self._easyocr_reader = easyocr.Reader(
                easyocr_langs,
                gpu=self.use_gpu,
                verbose=False,
            )
        return self._easyocr_reader

    def preprocess(self, image: Image.Image, for_tesseract: bool = True) -> Image.Image:
        """Preprocess image for better OCR accuracy on screenshots."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Handle large screenshots - keep more detail for Tesseract
        max_dim = 3500 if for_tesseract else (4000 if self.use_gpu else 2500)
        if max(image.size) > max_dim:
            ratio = max_dim / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        # Slight contrast boost helps with UI text
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)

        # Slight sharpening for text clarity
        image = image.filter(ImageFilter.SHARPEN)

        return image

    def extract_with_tesseract(self, image: Image.Image) -> str:
        """Extract text using Tesseract (fast CPU)."""
        import pytesseract

        processed = self.preprocess(image, for_tesseract=True)

        # Tesseract config for screenshot text
        # PSM 11 = Sparse text - good for UI with scattered text
        # OEM 3 = Default, use whatever is available
        lang_str = "+".join(self.languages)
        config = "--psm 11 --oem 3"

        text = pytesseract.image_to_string(processed, lang=lang_str, config=config)
        return text.strip()

    def extract_with_easyocr(self, image: Image.Image) -> str:
        """Extract text using EasyOCR (better with GPU)."""
        processed = self.preprocess(image, for_tesseract=False)
        img_array = np.array(processed)

        results = self.easyocr_reader.readtext(
            img_array,
            detail=0,
            paragraph=True,
            width_ths=0.7,
            batch_size=4 if self.use_gpu else 1,
        )

        return "\n".join(results)

    def extract_text(self, filepath: str) -> str:
        """Extract text from image file."""
        image = Image.open(filepath)

        # Use Tesseract if available and preferred (faster on CPU)
        if self.prefer_tesseract and self.tesseract_available and not self.use_gpu:
            try:
                return self.extract_with_tesseract(image)
            except Exception as e:
                logger.warning(f"Tesseract failed, falling back to EasyOCR: {e}")

        # Use EasyOCR (better with GPU, or as fallback)
        return self.extract_with_easyocr(image)


@lru_cache(maxsize=1)
def get_ocr_processor() -> OCRProcessor:
    """Get singleton OCR processor instance."""
    # Tesseract is better for terminal/code text, use it by default
    logger.info("Creating OCR processor (preferring Tesseract for code/terminal)")
    return OCRProcessor(use_gpu=False, prefer_tesseract=True)
