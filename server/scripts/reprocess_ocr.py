#!/usr/bin/env python3
"""Re-process all captures with Kimi K2.5 vision OCR (via Ollama).

Usage:
    python scripts/reprocess_ocr.py              # Process captures with poor OCR
    python scripts/reprocess_ocr.py --force      # Re-process ALL captures
    python scripts/reprocess_ocr.py --limit 100  # Process only 100 captures
"""

import argparse
import asyncio
import base64
import sys
from pathlib import Path

import httpx
from sqlalchemy import select, func

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jarvis_server.db.session import async_session_factory
from jarvis_server.db.models import Capture

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "kimi-k2.5:cloud"


async def check_ollama() -> bool:
    """Check if Ollama is running and model is available."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            if MODEL in models:
                return True
            print(f"ERROR: Model {MODEL} not found. Available: {models}")
            return False
    except Exception as e:
        print(f"ERROR: Ollama not reachable: {e}")
        return False


async def extract_with_ollama(filepath: str) -> str:
    """Extract text using Ollama vision model."""
    with open(filepath, "rb") as f:
        img_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": "Extract all visible text from this screenshot. Include window titles, app names, menu items, and all readable content. Be thorough and complete.",
                "images": [img_data],
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json().get("response", "")


def needs_reprocessing(ocr_text: str | None) -> bool:
    """Check if OCR text looks like garbage Tesseract output."""
    if not ocr_text:
        return True
    if len(ocr_text) < 50:
        return True
    # Check for common Tesseract garbage patterns
    garbage_ratio = sum(1 for c in ocr_text if c in "~|}{[]\\") / max(len(ocr_text), 1)
    if garbage_ratio > 0.1:
        return True
    return False


async def reprocess_all(force: bool = False, limit: int | None = None):
    """Re-process captures with vision OCR."""
    
    # Check Ollama first
    if not await check_ollama():
        print("Aborting: Ollama not available")
        return
    
    print(f"Using model: {MODEL}")
    print(f"Force mode: {force}")
    print(f"Limit: {limit or 'none'}")
    print()
    
    async with async_session_factory() as session:
        # Count total
        count_result = await session.execute(select(func.count(Capture.id)))
        total_in_db = count_result.scalar()
        print(f"Total captures in database: {total_in_db}")
        
        # Build query
        query = select(Capture).order_by(Capture.timestamp.desc())
        if limit:
            query = query.limit(limit)
        
        result = await session.execute(query)
        captures = result.scalars().all()
        
        processed = 0
        skipped = 0
        errors = 0
        
        for i, capture in enumerate(captures):
            capture_num = i + 1
            
            # Check if needs reprocessing
            if not force and not needs_reprocessing(capture.ocr_text):
                skipped += 1
                continue
            
            # Check file exists
            if not Path(capture.filepath).exists():
                print(f"[{capture_num}] SKIP - File missing: {capture.filepath}")
                skipped += 1
                continue
            
            try:
                print(f"[{capture_num}] Processing {capture.id[:8]}... ", end="", flush=True)
                new_ocr = await extract_with_ollama(capture.filepath)
                
                # Update in DB
                capture.ocr_text = new_ocr
                await session.commit()
                
                processed += 1
                print(f"OK ({len(new_ocr)} chars)")
                
            except Exception as e:
                errors += 1
                print(f"ERROR: {e}")
                continue
        
        print()
        print("=" * 50)
        print(f"COMPLETE")
        print(f"  Processed: {processed}")
        print(f"  Skipped:   {skipped}")
        print(f"  Errors:    {errors}")


def main():
    parser = argparse.ArgumentParser(description="Re-process captures with Kimi K2.5 OCR")
    parser.add_argument("--force", action="store_true", help="Re-process all, even with existing OCR")
    parser.add_argument("--limit", type=int, help="Limit number of captures to process")
    args = parser.parse_args()
    
    asyncio.run(reprocess_all(force=args.force, limit=args.limit))


if __name__ == "__main__":
    main()
