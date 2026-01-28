# Vision OCR Upgrade

**Status:** ✅ Completed and pushed to `master`  
**Linear Issue:** 7-291  
**Commit:** `6a4f31c`

## What Changed

Replaced Tesseract OCR as the primary text extraction method with **Claude 3.5 Sonnet Vision**, addressing poor text recognition on ultrawide screenshots.

## Implementation Details

### New Method: `extract_with_vision()`
- Uses Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) for OCR
- Handles multiple image formats: PNG, JPEG, WebP, GIF
- Specialized prompt for UI text extraction:
  - Window titles and app names
  - Readable text content
  - Menu items, buttons, labels
  - Terminal/console output
  - Code snippets

### Updated Method: `extract_text()`
Implements a robust fallback chain:
1. **Vision Model** (primary) - Best quality, especially for ultrawide/complex UI
2. **Tesseract** (fallback) - Fast CPU-based OCR
3. **EasyOCR** (final fallback) - GPU-optimized or last resort

### Configuration
- New parameter: `use_vision=True` (default)
- Supports environment variables:
  - `JARVIS_ANTHROPIC_API_KEY` (preferred)
  - `ANTHROPIC_API_KEY` (fallback)
- Lazy client initialization for efficiency

### Tesseract Improvement
Updated PSM mode from 11 (sparse text) to 3 (full page) for better full-screenshot segmentation.

## Verification

### Test Script
Created `test_vision_ocr.py` to verify:
- ✓ Vision OCR initialization
- ✓ API key detection
- ✓ Fallback mechanism
- ✓ Tesseract availability

### Run Test
```bash
cd server
python test_vision_ocr.py
```

## Environment Setup

### Required
Set the Anthropic API key in your environment:
```bash
export JARVIS_ANTHROPIC_API_KEY="sk-ant-..."
# OR
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Docker/Production
Add to `.env` or docker-compose:
```yaml
environment:
  - JARVIS_ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

## Performance Considerations

### Vision Model
- **Pros:** Superior accuracy on complex UIs, handles ultrawide screenshots
- **Cons:** API latency (~2-5s per image), API costs
- **Cost:** ~$0.0048 per screenshot (4096 tokens @ $3/MTok output)

### Fallback Behavior
If vision fails (no API key, rate limit, network error):
1. Logs warning with error details
2. Automatically falls back to Tesseract
3. No user intervention required

## Definition of Done

- ✅ Vision model extracts text from screenshots
- ✅ Works with ultrawide monitors (no preprocessing size limits for vision)
- ✅ Fallback to Tesseract if API fails
- ✅ Committed and pushed to `master`
- ✅ Verification test created

## Next Steps

1. **Monitor performance:** Check logs for fallback frequency
2. **Cost tracking:** Monitor Anthropic API usage in production
3. **Optional optimization:** 
   - Consider caching results for duplicate screenshots
   - Add config option to disable vision for specific capture types
   - Implement rate limiting/batching if costs are high

## Files Modified

- `server/src/jarvis_server/processing/ocr.py` - Main implementation
- `server/test_vision_ocr.py` - Verification script (new)
