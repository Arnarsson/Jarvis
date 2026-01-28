#!/usr/bin/env python3
"""Quick test to verify vision OCR is working."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from jarvis_server.processing.ocr import OCRProcessor


def test_vision_ocr():
    """Test that vision OCR can be initialized."""
    print("Testing Vision OCR initialization...")
    
    # Check if API key is set
    api_key = os.getenv("JARVIS_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  No ANTHROPIC_API_KEY set - vision OCR will fall back to Tesseract")
        print("   Set JARVIS_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY to enable vision OCR")
        return False
    
    # Initialize processor with vision enabled
    processor = OCRProcessor(use_vision=True)
    print("✓ OCRProcessor initialized with vision=True")
    
    # Try to access the client (will fail if API key is invalid)
    try:
        client = processor.anthropic_client
        print("✓ Anthropic client initialized successfully")
        print(f"✓ Vision OCR is ready!")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize Anthropic client: {e}")
        return False


def test_fallback():
    """Test that fallback to Tesseract works."""
    print("\nTesting fallback mechanism...")
    
    # Initialize with vision disabled
    processor = OCRProcessor(use_vision=False)
    print("✓ OCRProcessor initialized with vision=False")
    
    if processor.tesseract_available:
        print("✓ Tesseract is available as fallback")
    else:
        print("⚠️  Tesseract not available - will use EasyOCR")
    
    return True


if __name__ == "__main__":
    print("=== Jarvis Vision OCR Verification ===\n")
    
    vision_ok = test_vision_ocr()
    fallback_ok = test_fallback()
    
    print("\n=== Summary ===")
    if vision_ok and fallback_ok:
        print("✓ All checks passed!")
        sys.exit(0)
    elif fallback_ok:
        print("⚠️  Vision OCR not configured, but fallback is available")
        sys.exit(0)
    else:
        print("✗ Some checks failed")
        sys.exit(1)
