"""OCR processor for screenshot text extraction.

Uses Claude Vision (best quality) with Tesseract/EasyOCR fallback.
"""

import base64
import logging
import os
import shutil
from functools import lru_cache

import anthropic
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
        use_vision: bool = True,
    ):
        self.languages = languages or ["eng", "dan"]
        self.use_gpu = use_gpu
        self.prefer_tesseract = prefer_tesseract
        self.use_vision = use_vision
        self._tesseract_available: bool | None = None
        self._easyocr_reader = None
        self._anthropic_client = None

    @property
    def anthropic_client(self) -> anthropic.Anthropic:
        """Lazy initialization of Anthropic client."""
        if self._anthropic_client is None:
            # Check JARVIS_ANTHROPIC_API_KEY first, fall back to ANTHROPIC_API_KEY
            api_key = os.getenv("JARVIS_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not set - cannot use vision OCR. "
                    "Set JARVIS_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY environment variable."
                )
            self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            logger.info("Initialized Anthropic client for vision OCR")
        return self._anthropic_client

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

    def extract_with_vision(self, filepath: str) -> str:
        """Extract text using Claude Vision (best quality for UI screenshots)."""
        with open(filepath, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # Determine media type based on file extension
        media_type = "image/png"
        if filepath.lower().endswith((".jpg", ".jpeg")):
            media_type = "image/jpeg"
        elif filepath.lower().endswith(".webp"):
            media_type = "image/webp"
        elif filepath.lower().endswith(".gif"):
            media_type = "image/gif"

        logger.info(f"Extracting text with Claude Vision from {filepath}")
        response = self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": img_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract all visible text from this screenshot. Include:\n"
                                "1. Window titles and app names\n"
                                "2. All readable text content\n"
                                "3. Menu items, buttons, labels\n"
                                "4. Terminal/console output\n"
                                "5. Code snippets if visible\n\n"
                                "Format as plain text, preserving layout where possible. "
                                "Be thorough and capture everything readable."
                            ),
                        },
                    ],
                }
            ],
        )
        return response.content[0].text

    def extract_with_tesseract(self, image: Image.Image) -> str:
        """Extract text using Tesseract (fast CPU)."""
        import pytesseract

        processed = self.preprocess(image, for_tesseract=True)

        # Tesseract config for screenshot text
        # PSM 3 = Fully automatic page segmentation - best for full screenshots
        # OEM 3 = Default, use whatever is available
        lang_str = "+".join(self.languages)
        config = "--psm 3 --oem 3"

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
        """Extract text from image file.
        
        Prioritizes Claude Vision (best quality, especially for ultrawide/complex UI),
        falls back to Tesseract/EasyOCR if vision fails or is disabled.
        """
        # Try vision model first if enabled (best quality for UI screenshots)
        if self.use_vision:
            try:
                return self.extract_with_vision(filepath)
            except Exception as e:
                logger.warning(f"Vision OCR failed, falling back to Tesseract: {e}")

        # Load image for traditional OCR methods
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
    # Vision model is best for UI screenshots, especially ultrawide monitors
    logger.info("Creating OCR processor (using Claude Vision for best quality)")
    return OCRProcessor(use_gpu=False, prefer_tesseract=True, use_vision=True)
