"""OCR processor for screenshot text extraction.

Uses local Ollama Vision (free) + Claude Vision (best quality) with Tesseract/EasyOCR fallback.
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
    """OCR processor with Ollama Vision (local), Claude Vision, Tesseract, and EasyOCR support."""

    def __init__(
        self,
        use_gpu: bool = False,
        languages: list[str] | None = None,
        prefer_tesseract: bool = True,
        use_vision: bool = True,
        prefer_local: bool = True,
    ):
        self.languages = languages or ["eng", "dan"]
        self.use_gpu = use_gpu
        self.prefer_tesseract = prefer_tesseract
        self.use_vision = use_vision
        self.prefer_local = prefer_local
        self._tesseract_available: bool | None = None
        self._easyocr_reader = None
        self._anthropic_client = None
        self._ollama_available: bool | None = None

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
    def ollama_available(self) -> bool:
        """Check if Ollama is running and has the vision model."""
        if self._ollama_available is None:
            try:
                import requests

                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    # Check if kimi-k2.5:cloud or any kimi model is available
                    has_kimi = any("kimi" in model.get("name", "") for model in models)
                    self._ollama_available = has_kimi
                    if has_kimi:
                        logger.info("Ollama Vision (Kimi K2.5) available")
                    else:
                        logger.info("Ollama running but Kimi model not found")
                else:
                    self._ollama_available = False
            except Exception as e:
                logger.debug(f"Ollama not available: {e}")
                self._ollama_available = False
        return self._ollama_available

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

    def extract_with_ollama_vision(self, filepath: str, model: str = "kimi-k2.5:cloud") -> str:
        """Extract text using local Ollama vision model (free, no API costs)."""
        import requests

        with open(filepath, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")

        logger.info(f"Extracting text with Ollama Vision ({model}) from {filepath}")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": "Extract all visible text from this screenshot. Include window titles, app names, all readable text content. Be thorough.",
                "images": [img_data],
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("response", "")

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
        
        Fallback chain:
        1. Ollama Vision (kimi-k2.5) - free, local, if prefer_local=True and available
        2. Claude Vision - paid, best quality for complex UI
        3. Tesseract/EasyOCR - free, traditional OCR
        """
        # Try local Ollama Vision first if preferred and available (free, no API costs)
        if self.prefer_local and self.use_vision and self.ollama_available:
            try:
                return self.extract_with_ollama_vision(filepath)
            except Exception as e:
                logger.warning(f"Ollama Vision OCR failed, falling back to Claude Vision: {e}")

        # Try Claude Vision if enabled (best quality for UI screenshots)
        if self.use_vision:
            try:
                return self.extract_with_vision(filepath)
            except Exception as e:
                logger.warning(f"Claude Vision OCR failed, falling back to Tesseract: {e}")

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
    # Prefer local Ollama Vision (free) → Claude Vision (paid) → Tesseract
    logger.info("Creating OCR processor (prefer local Ollama, fallback to Claude Vision)")
    return OCRProcessor(use_gpu=False, prefer_tesseract=True, use_vision=True, prefer_local=True)
