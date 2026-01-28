# Why + Confidence Plumbing — Implementation

**Issue:** Linear 7-295 (P0)  
**Date:** 2025-01-28  
**Status:** ✅ Complete

## Overview

This implements the "Why + Confidence" data contract and backend support for all Jarvis suggestions. Every suggestion now includes transparent explanations with confidence scores and links to source data.

## What Was Built

### 1. Data Models (`server/src/jarvis_server/api/models/`)

**`why_payload.py`** - Core Pydantic models:
- `WhyPayload` - Main explanation container
  - `reasons: list[str]` - Plain English explanations
  - `confidence: float` - 0-1 confidence score
  - `sources: list[Source]` - Pointers to original data
  
- `Source` - Pointer to source data
  - `type` - email | capture | calendar | chat | conversation
  - `id` - Unique identifier
  - `timestamp` - When the source was created
  - `snippet` - First ~200 chars preview
  - `url` - Optional open-in-context link

### 2. Helper Functions (`server/src/jarvis_server/api/helpers/`)

**`why_builder.py`** - Utilities to construct WhyPayloads:

- `build_why_payload()` - Generic builder from raw data
- `build_why_from_email()` - Email-specific builder
- `build_why_from_capture()` - Screen capture builder
- `build_why_from_calendar()` - Calendar event builder
- `build_why_from_conversation()` - AI conversation builder
- `build_why_from_pattern()` - Detected pattern builder
- `merge_why_payloads()` - Merge multiple explanations

### 3. API Endpoint (`server/src/jarvis_server/api/why.py`)

**New route:** `GET /api/why/{suggestion_type}/{id}`

Fetches full Why context for any suggestion type:
- `pattern` - Detected behavioral patterns
- `meeting` - Meetings and events
- `capture` - Screen captures
- `conversation` - AI conversations
- `calendar` - Calendar events

### 4. Integration with Existing Endpoints

**Updated:** `server/src/jarvis_server/api/patterns.py`

The patterns endpoint now includes WhyPayload in responses:
- `GET /api/v2/patterns` - List with Why context
- `PATCH /api/v2/patterns/{id}/status` - Status update with Why

## Usage Examples

### Basic Usage

```python
from jarvis_server.api.helpers import build_why_from_email

why = build_why_from_email(
    email_id="msg_12345",
    email_snippet="Can you send the proposal by Friday?",
    email_timestamp=datetime.now(timezone.utc),
    reasons=[
        "Sender is VIP contact",
        "Contains deadline mention",
        "Related to active project"
    ],
    confidence=0.85
)
```

### In API Responses

```python
from pydantic import BaseModel
from jarvis_server.api.models import WhyPayload

class MySuggestionResponse(BaseModel):
    id: str
    title: str
    # ... other fields ...
    why: WhyPayload  # Add to any suggestion response
```

### Fetching Full Context

```bash
# Get Why context for a pattern
curl http://localhost:8000/api/why/pattern/pat_abc123

# Get Why context for a meeting
curl http://localhost:8000/api/why/meeting/mtg_xyz789
```

### Response Example

```json
{
  "reasons": [
    "Detected 15 times over past month",
    "Pattern type: Time Habit",
    "Suggested action available"
  ],
  "confidence": 0.92,
  "sources": [
    {
      "type": "conversation",
      "id": "pat_abc123",
      "timestamp": "2025-01-28T10:30:00Z",
      "snippet": "You typically review email at 9am and 4pm",
      "url": "/workflows?pattern=pat_abc123"
    },
    {
      "type": "conversation",
      "id": "conv_1",
      "timestamp": "2025-01-28T10:30:00Z",
      "snippet": "Related conversation",
      "url": "/search?conversation=conv_1"
    }
  ]
}
```

## File Structure

```
server/src/jarvis_server/
├── api/
│   ├── models/
│   │   ├── __init__.py
│   │   └── why_payload.py          # Data models
│   ├── helpers/
│   │   ├── __init__.py
│   │   └── why_builder.py          # Helper functions
│   ├── examples/
│   │   └── why_usage.py            # Usage examples
│   ├── why.py                      # New API endpoint
│   └── patterns.py                 # Updated with Why support
└── main.py                         # Added why_router
```

## Definition of Done ✅

- [x] WhyPayload model created
- [x] Helper functions to build payloads (7 functions total)
- [x] At least one existing endpoint returns WhyPayload (patterns.py)
- [x] API endpoint to fetch full context (`GET /api/why/{type}/{id}`)
- [x] All files pass Python syntax check
- [x] Router registered in main.py
- [x] Usage examples documented

## Next Steps for Other Endpoints

To add Why support to other endpoints:

1. Import the models and helpers:
   ```python
   from jarvis_server.api.models import WhyPayload
   from jarvis_server.api.helpers import build_why_from_<type>
   ```

2. Add `why: WhyPayload | None = None` to your response model

3. Build the Why payload in your endpoint:
   ```python
   why = build_why_from_<type>(
       <type>_id=item.id,
       # ... other params ...
       reasons=["Reason 1", "Reason 2"],
       confidence=0.85
   )
   ```

4. Include in response: `why=why`

## Testing

Run syntax checks:
```bash
cd ~/Documents/jarvis
python3 -m py_compile server/src/jarvis_server/api/models/why_payload.py
python3 -m py_compile server/src/jarvis_server/api/helpers/why_builder.py
python3 -m py_compile server/src/jarvis_server/api/why.py
python3 -m py_compile server/src/jarvis_server/api/patterns.py
```

Run usage examples:
```bash
cd ~/Documents/jarvis
python3 server/src/jarvis_server/api/examples/why_usage.py
```

## Design Principles

1. **Transparency** - Every suggestion must explain itself
2. **Traceability** - Links back to source data
3. **Confidence** - Even rough heuristics are better than nothing
4. **Composability** - Easy to build and merge explanations
5. **Extensibility** - New source types can be added easily

## Related Files

- `.planning/SUPER-FEEDBACK-BRIEF.md` - Product requirements
- `WHY_CONFIDENCE_README.md` - This document
- Linear Issue 7-295 - Original ticket
