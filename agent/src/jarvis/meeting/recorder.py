"""Meeting audio recorder with consent gate.

This module provides audio recording capabilities for meetings,
requiring explicit user consent before any recording can begin.
Audio is captured from the system's audio input device and saved
as WAV files for later transcription.
"""

import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

logger = logging.getLogger(__name__)


class ConsentToken:
    """Represents user consent for audio recording.

    A consent token must be obtained and provided to start recording,
    ensuring audio capture only happens with explicit user action.
    """

    def __init__(self, meeting_id: str):
        self.meeting_id = meeting_id
        self.token = secrets.token_urlsafe(16)
        self.created_at = datetime.now(timezone.utc)
        self.valid = True

    def revoke(self) -> None:
        """Revoke this consent token."""
        self.valid = False


class MeetingRecorder:
    """Records meeting audio with consent verification.

    Audio recording requires explicit consent through a ConsentToken.
    This ensures recordings only happen when the user has actively
    agreed to record the meeting.

    Attributes:
        sample_rate: Audio sample rate in Hz (default 16kHz for speech)
        channels: Number of audio channels (default 1/mono)
        data_dir: Directory to save audio files
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        data_dir: Optional[Path] = None,
    ):
        """Initialize the recorder.

        Args:
            sample_rate: Sample rate in Hz (16000 optimal for speech recognition)
            channels: Number of channels (1 for mono)
            data_dir: Directory for audio files (defaults to JARVIS_DATA_DIR/meetings/audio)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.data_dir = (
            data_dir
            or Path(os.getenv("JARVIS_DATA_DIR", "/tmp/jarvis")) / "meetings" / "audio"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._stream: Optional[sd.InputStream] = None
        self._frames: list[np.ndarray] = []
        self._consent_token: Optional[ConsentToken] = None
        self._current_meeting_id: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        """Check if recording is currently active."""
        return self._recording

    @property
    def has_consent(self) -> bool:
        """Check if valid consent exists for recording."""
        return self._consent_token is not None and self._consent_token.valid

    def request_consent(self, meeting_id: str) -> ConsentToken:
        """Create a consent token for recording.

        The user must explicitly provide this token to start recording.
        This ensures recording only happens with explicit user action.

        Args:
            meeting_id: The meeting to associate with the recording

        Returns:
            ConsentToken that must be passed to start_recording
        """
        token = ConsentToken(meeting_id)
        logger.info(
            "recording_consent_requested meeting_id=%s token=%s...",
            meeting_id,
            token.token[:8],
        )
        return token

    def start_recording(self, consent_token: ConsentToken) -> bool:
        """Start audio recording with verified consent.

        Args:
            consent_token: Token from request_consent - proves user consented

        Returns:
            True if recording started, False if consent invalid or already recording
        """
        if self._recording:
            logger.warning("recording_already_active")
            return False

        if not consent_token.valid:
            logger.warning("recording_consent_invalid")
            return False

        self._consent_token = consent_token
        self._current_meeting_id = consent_token.meeting_id
        self._frames = []
        self._recording = True

        def audio_callback(
            indata: np.ndarray, frames: int, time_info: object, status: object
        ) -> None:
            if status:
                logger.warning("audio_status status=%s", str(status))
            if self._recording:
                self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                callback=audio_callback,
            )
            self._stream.start()
            logger.info(
                "recording_started meeting_id=%s sample_rate=%s",
                self._current_meeting_id,
                self.sample_rate,
            )
            return True

        except Exception as e:
            logger.error("recording_start_failed error=%s", str(e))
            self._recording = False
            return False

    def stop_recording(self) -> Optional[Path]:
        """Stop recording and save audio to file.

        Returns:
            Path to saved audio file, or None if no recording was active
        """
        if not self._recording:
            return None

        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            logger.warning("recording_stopped_no_audio")
            return None

        # Concatenate frames
        audio_data = np.concatenate(self._frames, axis=0)

        # Convert to int16 for WAV
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Save to file
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"meeting_{self._current_meeting_id}_{timestamp}.wav"
        filepath = self.data_dir / filename

        wavfile.write(str(filepath), self.sample_rate, audio_int16)

        duration = len(audio_data) / self.sample_rate
        logger.info(
            "recording_saved meeting_id=%s filepath=%s duration_seconds=%s file_size=%s",
            self._current_meeting_id,
            str(filepath),
            round(duration, 2),
            filepath.stat().st_size,
        )

        # Revoke consent token
        if self._consent_token:
            self._consent_token.revoke()
            self._consent_token = None

        self._current_meeting_id = None
        self._frames = []

        return filepath

    def get_audio_devices(self) -> list[dict]:
        """List available audio input devices.

        Returns:
            List of device info dicts with keys: index, name, channels,
            sample_rate, is_default
        """
        devices = sd.query_devices()
        input_devices = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                input_devices.append(
                    {
                        "index": i,
                        "name": d["name"],
                        "channels": d["max_input_channels"],
                        "sample_rate": d["default_samplerate"],
                        "is_default": i == sd.default.device[0],
                    }
                )
        return input_devices

    def set_device(self, device_index: int) -> None:
        """Set the audio input device to use.

        Args:
            device_index: Index of the device from get_audio_devices()
        """
        sd.default.device = (device_index, None)
        logger.info("audio_device_set device_index=%s", device_index)
