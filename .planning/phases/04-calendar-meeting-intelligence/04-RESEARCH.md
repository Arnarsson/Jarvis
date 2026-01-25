# Phase 4: Calendar & Meeting Intelligence - Research

**Researched:** 2026-01-25
**Domain:** Google Calendar Integration, Meeting Detection, Audio Transcription, Meeting Summarization
**Confidence:** MEDIUM-HIGH

## Summary

This phase requires integrating five distinct capabilities: Google Calendar two-way sync, meeting detection, audio capture, speech-to-text transcription, and meeting summarization with action item extraction. The existing Jarvis infrastructure (FastAPI, PostgreSQL, Qdrant, ARQ workers) provides a solid foundation.

The standard approach uses:
- **google-api-python-client** with OAuth2 for calendar access (push notifications + incremental sync)
- **Window title detection** via existing pywinctl integration for meeting detection
- **python-sounddevice** for audio capture on Linux (PipeWire/PulseAudio compatible)
- **faster-whisper** for self-hosted speech-to-text (4x faster than OpenAI Whisper, runs on server GPU)
- **LLM API** (Anthropic/OpenAI) for structured meeting summaries and action item extraction

**Primary recommendation:** Build the calendar sync first (foundation for meeting detection), then layer meeting detection, audio capture, transcription, and summarization as progressive enhancements.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-api-python-client | 2.187.0+ | Google Calendar API | Official Google library, production-proven, full API coverage |
| google-auth-oauthlib | 1.2.0+ | OAuth2 flow | Official auth library, handles token refresh |
| faster-whisper | 1.0.0+ | Speech-to-text | 4x faster than OpenAI Whisper, CTranslate2 backend, lower memory |
| python-sounddevice | 0.5.0+ | Audio capture | Cross-platform, NumPy integration, PipeWire/PulseAudio support |
| pywinctl | 0.4.0+ | Window detection | Already in project, cross-platform active window info |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| whisperx | 3.1.0+ | Transcription + diarization | When speaker identification needed (multi-person meetings) |
| pyannote-audio | 3.3.0+ | Speaker diarization | Required by WhisperX for speaker separation |
| scipy | 1.14.0+ | Audio file handling | WAV file read/write alongside sounddevice |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| faster-whisper | OpenAI Whisper API | Cloud API has privacy concerns, costs per minute |
| faster-whisper | whisper.cpp | C++ binding, harder to integrate with Python pipeline |
| python-sounddevice | PyAudio | PyAudio has harder dependencies, less Pythonic API |
| Window detection | Calendar-based only | Misses ad-hoc meetings, less accurate |

**Installation:**
```bash
# Calendar integration
pip install google-api-python-client google-auth-oauthlib

# Audio capture and transcription
pip install python-sounddevice scipy
pip install faster-whisper  # Requires CUDA 12 + cuDNN 9 for GPU

# Optional: Speaker diarization
pip install whisperx  # Includes pyannote-audio
```

## Architecture Patterns

### Recommended Project Structure
```
server/src/jarvis_server/
├── calendar/                # NEW: Calendar integration
│   ├── __init__.py
│   ├── oauth.py            # OAuth2 flow, token management
│   ├── sync.py             # Incremental sync logic
│   ├── webhooks.py         # Push notification handlers
│   └── models.py           # CalendarEvent SQLAlchemy model
├── meetings/               # NEW: Meeting intelligence
│   ├── __init__.py
│   ├── detection.py        # Meeting detection logic
│   ├── audio.py            # Audio capture coordination
│   ├── briefs.py           # Pre-meeting brief generation
│   └── summaries.py        # Post-meeting summarization
├── transcription/          # NEW: Speech-to-text
│   ├── __init__.py
│   ├── whisper.py          # faster-whisper wrapper
│   └── tasks.py            # ARQ transcription tasks
└── api/
    ├── calendar.py         # NEW: Calendar API endpoints
    └── meetings.py         # NEW: Meeting API endpoints

agent/src/jarvis/
├── meeting/                # NEW: Desktop-side meeting support
│   ├── __init__.py
│   ├── detector.py         # Window-based meeting detection
│   └── recorder.py         # Audio recording with consent
```

### Pattern 1: OAuth2 Desktop Flow with Token Persistence
**What:** User authorizes once, tokens stored and auto-refreshed
**When to use:** Server-side calendar access for a single user
**Example:**
```python
# Source: google-auth-oauthlib official docs
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_PATH = Path('/data/calendar/token.json')
CREDS_PATH = Path('/data/calendar/credentials.json')

def get_calendar_service():
    """Get authenticated Calendar API service."""
    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or reauthorize if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next time
        TOKEN_PATH.write_text(creds.to_json())

    return build('calendar', 'v3', credentials=creds)
```

### Pattern 2: Incremental Calendar Sync with Sync Tokens
**What:** Fetch only changed events since last sync
**When to use:** Regular calendar polling (every 5-15 minutes)
**Example:**
```python
# Source: Google Calendar API sync documentation
async def incremental_sync(db: AsyncSession, service) -> list[dict]:
    """Sync calendar changes using sync tokens."""
    # Get stored sync token
    sync_state = await db.get(SyncState, 'calendar')
    sync_token = sync_state.token if sync_state else None

    try:
        if sync_token:
            # Incremental sync
            events = service.events().list(
                calendarId='primary',
                syncToken=sync_token
            ).execute()
        else:
            # Full sync (first time or after 410)
            events = service.events().list(
                calendarId='primary',
                maxResults=2500,
                singleEvents=True
            ).execute()

        # Process all pages
        all_items = events.get('items', [])
        while 'nextPageToken' in events:
            events = service.events().list(
                calendarId='primary',
                pageToken=events['nextPageToken'],
                syncToken=sync_token
            ).execute()
            all_items.extend(events.get('items', []))

        # Store new sync token
        new_token = events.get('nextSyncToken')
        if new_token:
            await save_sync_token(db, 'calendar', new_token)

        return all_items

    except HttpError as e:
        if e.resp.status == 410:
            # Token expired - full resync needed
            await delete_sync_token(db, 'calendar')
            return await incremental_sync(db, service)
        raise
```

### Pattern 3: Meeting Detection via Window Title
**What:** Detect meeting apps via active window monitoring
**When to use:** Complement calendar data with real-time detection
**Example:**
```python
# Source: Extending existing pywinctl integration
import re

MEETING_PATTERNS = [
    # Zoom
    (r'zoom\s*(meeting|webinar)?', 'zoom'),
    (r'zoom\.us', 'zoom'),
    # Google Meet
    (r'meet\.google\.com', 'google_meet'),
    (r'google meet', 'google_meet'),
    # Microsoft Teams
    (r'microsoft teams', 'teams'),
    (r'\| meeting \|.*teams', 'teams'),
    # Generic
    (r'(meeting|call)\s+with', 'generic'),
]

def detect_meeting(window_info: WindowInfo) -> tuple[bool, str | None]:
    """Check if current window indicates an active meeting."""
    if not window_info:
        return False, None

    text = f"{window_info.app_name} {window_info.window_title}".lower()

    for pattern, platform in MEETING_PATTERNS:
        if re.search(pattern, text):
            return True, platform

    return False, None
```

### Pattern 4: Audio Recording with Consent Gate
**What:** Record only with explicit consent, stop when meeting ends
**When to use:** Any audio capture scenario
**Example:**
```python
# Source: python-sounddevice docs + privacy pattern
import sounddevice as sd
import numpy as np
from scipy.io import wavfile

class MeetingRecorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.frames = []
        self.consent_given = False

    def start(self, consent_token: str) -> bool:
        """Start recording if consent verified."""
        if not self._verify_consent(consent_token):
            return False

        self.consent_given = True
        self.recording = True
        self.frames = []

        def callback(indata, frames, time, status):
            if self.recording:
                self.frames.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=callback
        )
        self.stream.start()
        return True

    def stop(self) -> np.ndarray | None:
        """Stop recording and return audio data."""
        if not self.recording:
            return None

        self.recording = False
        self.stream.stop()
        self.stream.close()

        if self.frames:
            return np.concatenate(self.frames, axis=0)
        return None
```

### Pattern 5: faster-whisper Transcription Pipeline
**What:** GPU-accelerated transcription with batching
**When to use:** Processing meeting audio after recording
**Example:**
```python
# Source: faster-whisper GitHub docs
from faster_whisper import WhisperModel
from pathlib import Path

class TranscriptionService:
    def __init__(self, model_size: str = "large-v3", device: str = "cuda"):
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type="float16" if device == "cuda" else "int8"
        )

    def transcribe(self, audio_path: Path) -> dict:
        """Transcribe audio file with timestamps."""
        segments, info = self.model.transcribe(
            str(audio_path),
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,  # Remove silence
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        result = {
            "language": info.language,
            "duration": info.duration,
            "segments": []
        }

        for segment in segments:
            result["segments"].append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in (segment.words or [])
                ]
            })

        return result
```

### Pattern 6: Pre-Meeting Brief via Memory Search
**What:** Query existing memory for relevant context before meetings
**When to use:** Generating briefings 15-30 minutes before meetings
**Example:**
```python
# Source: Extending existing search_memory tool
from datetime import datetime, timedelta

async def generate_pre_meeting_brief(
    event: CalendarEvent,
    memory_service: MemoryService,
    llm_client: LLMClient
) -> str:
    """Generate contextual brief for upcoming meeting."""

    # Extract search terms from meeting
    search_terms = []
    if event.summary:
        search_terms.append(event.summary)
    if event.attendees:
        search_terms.extend([a.email.split('@')[0] for a in event.attendees[:5]])

    # Search memory for relevant context
    context_results = []
    for term in search_terms[:3]:  # Limit queries
        results = await memory_service.search(
            query=term,
            limit=5,
            start_date=datetime.now() - timedelta(days=30)
        )
        context_results.extend(results)

    # Deduplicate and rank
    unique_results = deduplicate_by_id(context_results)[:10]

    # Generate brief with LLM
    prompt = f"""Generate a pre-meeting brief for: {event.summary}

Attendees: {', '.join(a.display_name or a.email for a in event.attendees[:5])}
Time: {event.start}
Description: {event.description or 'No description'}

Relevant context from memory:
{format_results(unique_results)}

Create a brief covering:
1. Key context about this meeting topic
2. Recent interactions with attendees
3. Open questions or action items to follow up on
"""

    return await llm_client.generate(prompt)
```

### Anti-Patterns to Avoid
- **Polling Calendar Every Minute:** Use push notifications + 15-minute incremental sync fallback
- **Recording Without Explicit Consent:** Always require user action to start recording
- **Processing Audio Synchronously:** Queue transcription jobs to ARQ worker
- **Single Large Transcript to LLM:** Chunk long meetings, use map-reduce summarization
- **Hardcoding Meeting Detection Patterns:** Make patterns configurable for new apps

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth2 token management | Custom token storage/refresh | google-auth-oauthlib Credentials class | Handles edge cases, token refresh, expiration |
| Audio capture on Linux | Direct ALSA/PulseAudio calls | python-sounddevice | Abstracts PipeWire/PulseAudio, handles streams |
| Speech recognition | Train own model | faster-whisper | State-of-the-art accuracy, GPU optimization built-in |
| Meeting summarization | Rule-based extraction | LLM with structured prompts | Handles context, generates coherent summaries |
| Calendar sync | Manual event tracking | Google sync tokens | Handles deletions, ACL changes, pagination |
| Speaker separation | Heuristics based on silence | pyannote-audio diarization | Neural network-based, handles overlapping speech |

**Key insight:** Calendar integration and speech-to-text are solved problems with mature libraries. Focus implementation effort on the intelligence layer (brief generation, action item extraction) where custom logic adds value.

## Common Pitfalls

### Pitfall 1: OAuth2 Token Expiration During Background Tasks
**What goes wrong:** Sync job fails at 3 AM because token expired, no user to re-auth
**Why it happens:** Access tokens expire in 1 hour, refresh tokens can be revoked
**How to avoid:** Always request `access_type='offline'` for refresh tokens, implement proactive token refresh before expiration
**Warning signs:** HTTP 401 errors in calendar sync logs

### Pitfall 2: Push Notification Webhook Security
**What goes wrong:** Attacker spoofs calendar notifications, injects fake events
**Why it happens:** Webhook endpoint is public, no verification of notification source
**How to avoid:** Verify `X-Goog-Channel-Token` matches your stored token, validate `X-Goog-Resource-ID`
**Warning signs:** Unexpected events appearing in sync

### Pitfall 3: Audio Capture Device Selection
**What goes wrong:** Records wrong audio source (e.g., system sounds instead of meeting)
**Why it happens:** Multiple audio devices, wrong default selected
**How to avoid:** Let user select/configure audio device, verify device before recording
**Warning signs:** Transcription contains music, notifications, or silence

### Pitfall 4: Transcription Hallucination on Silence
**What goes wrong:** Whisper generates plausible but non-existent text during silence
**Why it happens:** Known Whisper behavior when audio has long pauses
**How to avoid:** Enable VAD filter (`vad_filter=True`), use `no_speech_threshold`
**Warning signs:** Repetitive phrases, text unrelated to meeting topic

### Pitfall 5: Meeting Detection False Positives
**What goes wrong:** Brief generated for YouTube video about "Zoom meeting tips"
**Why it happens:** Window title matching too broad
**How to avoid:** Combine window detection with calendar correlation, require both
**Warning signs:** Briefs for non-meetings, excessive detection frequency

### Pitfall 6: Webhook Channel Expiration
**What goes wrong:** Push notifications stop after 24 hours without warning
**Why it happens:** Google Calendar webhook channels expire
**How to avoid:** Track channel expiration, renew proactively (e.g., every 20 hours)
**Warning signs:** Sudden stop of real-time calendar updates

### Pitfall 7: Long Meeting Transcription Timeout
**What goes wrong:** 2-hour meeting transcription times out or OOMs
**Why it happens:** Processing entire audio at once
**How to avoid:** Chunk audio into segments, process with batched inference
**Warning signs:** Worker job timeouts, high memory usage

## Code Examples

Verified patterns from official sources:

### Google Calendar Events List
```python
# Source: Google Calendar API Python Quickstart
from googleapiclient.discovery import build
from datetime import datetime, timezone

def list_upcoming_events(service, max_results: int = 10) -> list[dict]:
    """List upcoming calendar events."""
    now = datetime.now(timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])
```

### Webhook Watch Setup
```python
# Source: Google Calendar Push Notifications docs
import uuid

def setup_calendar_watch(service, webhook_url: str) -> dict:
    """Register webhook for calendar change notifications."""
    channel_id = str(uuid.uuid4())

    body = {
        'id': channel_id,
        'type': 'web_hook',
        'address': webhook_url,  # Must be HTTPS with valid cert
        'token': generate_secure_token(),  # For verification
        'expiration': int((datetime.now() + timedelta(hours=20)).timestamp() * 1000)
    }

    return service.events().watch(
        calendarId='primary',
        body=body
    ).execute()
```

### faster-whisper with VAD
```python
# Source: faster-whisper GitHub README
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")

segments, info = model.transcribe(
    "meeting.wav",
    beam_size=5,
    vad_filter=True,
    vad_parameters=dict(
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=500,
        speech_pad_ms=400
    )
)

print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
```

### Action Item Extraction Prompt
```python
# Source: AWS/AssemblyAI best practices
ACTION_ITEM_PROMPT = """Analyze this meeting transcript and extract action items.

<transcript>
{transcript}
</transcript>

For each action item, identify:
- Task description (what needs to be done)
- Assigned owner (who is responsible, if mentioned)
- Due date (if specified)
- Priority (high/medium/low based on urgency cues)

Return as JSON:
{
  "summary": "2-3 sentence meeting summary",
  "action_items": [
    {
      "task": "string",
      "owner": "string or null",
      "due_date": "string or null",
      "priority": "high|medium|low"
    }
  ],
  "key_decisions": ["string"],
  "follow_ups": ["string"]
}

Focus on concrete, actionable items. Ignore general discussion points."""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI Whisper direct | faster-whisper (CTranslate2) | 2023 | 4x speed, 50% memory reduction |
| Speaker ID via energy | pyannote neural diarization | 2024 | Much better accuracy for overlapping speech |
| Calendar polling every minute | Push notifications + sync tokens | Always available | Reduced API calls, near-real-time updates |
| Full calendar resync | Incremental sync with tokens | Always available | Only fetch changes, handle deletions |
| Rule-based summarization | LLM with structured prompts | 2023-2024 | Human-quality summaries, better action items |

**Deprecated/outdated:**
- **EasyOCR for audio**: EasyOCR is for images; confusion sometimes occurs
- **Whisper large-v2**: Superseded by large-v3 and turbo models
- **caldav library**: Works but google-api-python-client is better for Google Calendar specifically

## Open Questions

Things that couldn't be fully resolved:

1. **Audio Source for Virtual Meetings**
   - What we know: python-sounddevice captures from default input device
   - What's unclear: Best method to capture meeting audio that includes other participants (need loopback)
   - Recommendation: Research PipeWire loopback setup (`pw-loopback`), may need desktop config

2. **Webhook HTTPS Requirement**
   - What we know: Google requires valid SSL certificate on webhook endpoint
   - What's unclear: How to handle with Tailscale-only setup (no public endpoint)
   - Recommendation: Use polling-only sync, or expose webhook via Cloudflare Tunnel if needed

3. **Multi-Calendar Support**
   - What we know: API supports multiple calendar IDs
   - What's unclear: UX for selecting which calendars to sync
   - Recommendation: Start with primary calendar only, add multi-calendar in v2

## Sources

### Primary (HIGH confidence)
- [Google Calendar API Python Quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)
- [Google Calendar Push Notifications](https://developers.google.com/workspace/calendar/api/guides/push)
- [Google Calendar Sync Guide](https://developers.google.com/workspace/calendar/api/guides/sync)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) - Installation, API, benchmarks
- [WhisperX GitHub](https://github.com/m-bain/whisperX) - Diarization setup
- [python-sounddevice docs](https://python-sounddevice.readthedocs.io/)
- [google-api-python-client PyPI](https://pypi.org/project/google-api-python-client/) - v2.187.0

### Secondary (MEDIUM confidence)
- [AWS Meeting Summarization with Amazon Nova](https://aws.amazon.com/blogs/machine-learning/meeting-summarization-and-action-item-extraction-with-amazon-nova/) - Prompt engineering patterns
- [AssemblyAI: How to Summarize Meetings with LLMs](https://www.assemblyai.com/blog/summarize-meetings-llms-python) - Best practices
- [PipeWire Loopback Documentation](https://docs.pipewire.org/page_module_loopback.html) - Audio routing
- [Modal: Choosing Between Whisper Variants](https://modal.com/blog/choosing-whisper-variants) - Performance comparison
- [Arch Wiki: Zoom Meetings](https://wiki.archlinux.org/title/Zoom_Meetings) - Linux meeting app behavior

### Tertiary (LOW confidence)
- WebSearch results for meeting detection patterns - needs validation with actual testing
- Pre-meeting brief generation patterns - limited production references found

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official libraries, well-documented APIs
- Architecture: MEDIUM-HIGH - Patterns follow established Jarvis architecture
- Calendar integration: HIGH - Official Google documentation
- Audio capture: MEDIUM - Linux-specific, needs device testing
- Transcription: HIGH - faster-whisper well-documented, benchmarked
- Meeting summarization: MEDIUM - LLM prompts need tuning
- Meeting detection: MEDIUM - Window patterns need validation

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days - stable domain, but LLM practices evolving)
