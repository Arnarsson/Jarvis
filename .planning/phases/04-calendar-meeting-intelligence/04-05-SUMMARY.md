---
phase: 04-calendar-meeting-intelligence
plan: 05
subsystem: meeting-intelligence
tags: [audio, recording, consent, upload, transcription]
depends_on:
  requires: [04-03]
  provides: [audio-recording, consent-gate, audio-upload-api]
  affects: [04-06, 04-07]
tech-stack:
  added: [sounddevice, scipy, numpy]
  patterns: [consent-token, lazy-directory-creation]
key-files:
  created:
    - agent/src/jarvis/meeting/recorder.py
  modified:
    - agent/pyproject.toml
    - agent/src/jarvis/meeting/__init__.py
    - server/src/jarvis_server/api/meetings.py
decisions:
  - "ConsentToken pattern for explicit recording consent"
  - "16kHz mono audio for speech recognition optimization"
  - "Lazy directory creation to avoid permission errors at import"
  - "Consent verification at upload endpoint"
metrics:
  duration: 3 min
  completed: 2026-01-25
---

# Phase 04 Plan 05: Meeting Audio Capture Summary

**One-liner:** Audio recording with consent-gate pattern using sounddevice, WAV output, and server upload with consent verification

## What Was Built

### Agent: Meeting Audio Recorder (`agent/src/jarvis/meeting/recorder.py`)

**ConsentToken class:**
- Cryptographically secure token (secrets.token_urlsafe)
- Associated with specific meeting_id
- Valid/revoked state tracking
- Auto-revoked after recording stops

**MeetingRecorder class:**
- Requires ConsentToken to start recording
- Audio capture at 16kHz mono (optimal for speech recognition)
- sounddevice InputStream with callback for frame accumulation
- WAV output via scipy.io.wavfile
- Device listing and selection for audio input
- Configurable data directory (JARVIS_DATA_DIR/meetings/audio)

### Server: Audio Upload API (`server/src/jarvis_server/api/meetings.py`)

**POST /api/meetings/consent/{meeting_id}:**
- Records user consent for a meeting
- Updates meeting.consent_given = True

**POST /api/meetings/audio/{meeting_id}:**
- Validates meeting exists
- Verifies consent_given before accepting upload
- Accepts only WAV files
- Saves to JARVIS_DATA_DIR/meetings/audio/
- Updates meeting.audio_path and transcript_status
- Queues transcription task (graceful failure if Redis unavailable)

## Consent Flow

```
1. Agent detects meeting start (04-03)
2. Agent calls request_consent(meeting_id) -> ConsentToken
3. User explicitly approves recording (provides token)
4. Agent POSTs to /api/meetings/consent/{meeting_id}
5. Agent calls start_recording(consent_token)
6. Meeting ends -> stop_recording() returns WAV path
7. Agent POSTs WAV to /api/meetings/audio/{meeting_id}
8. Server queues transcription task
```

## Key Implementation Details

**Audio capture configuration:**
- Sample rate: 16000 Hz (speech recognition standard)
- Channels: 1 (mono)
- Format: float32 internally, int16 in WAV
- Callback-based streaming for memory efficiency

**Lazy directory creation:**
```python
def _get_audio_storage_path() -> Path:
    path = Path(os.getenv("JARVIS_DATA_DIR", "/data")) / "meetings" / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path
```
This avoids PermissionError at module import time when /data doesn't exist.

## Files Changed

| File | Change |
|------|--------|
| agent/pyproject.toml | Added sounddevice, scipy, numpy dependencies |
| agent/src/jarvis/meeting/recorder.py | New: Audio recorder with consent gate |
| agent/src/jarvis/meeting/__init__.py | Export ConsentToken, MeetingRecorder |
| server/src/jarvis_server/api/meetings.py | Added audio upload and consent endpoints |

## Verification Results

- [x] Audio dependencies installed (sounddevice, scipy, numpy)
- [x] MeetingRecorder requires ConsentToken before recording
- [x] Audio saved as WAV file with meeting ID in filename
- [x] Server has POST /api/meetings/audio/{meeting_id} endpoint
- [x] Server has POST /api/meetings/consent/{meeting_id} endpoint
- [x] Upload validates consent_given before accepting

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy directory creation for audio storage**
- **Found during:** Task 3 verification
- **Issue:** AUDIO_STORAGE_PATH.mkdir() at module level caused PermissionError when /data doesn't exist
- **Fix:** Changed to lazy _get_audio_storage_path() function called only when needed
- **Files modified:** server/src/jarvis_server/api/meetings.py
- **Commit:** 649cedc

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 48e8b2c | chore | Add audio capture dependencies |
| 0b03bac | feat | Implement meeting audio recorder with consent gate |
| 649cedc | feat | Add audio upload and consent recording endpoints |

## Next Phase Readiness

**Prerequisites for 04-06 (Transcription):**
- [x] Audio files saved in known location
- [x] transcript_status field updated to "pending"
- [x] Meeting ID associated with audio
- [x] faster-whisper already in server dependencies

**Open questions:** None
