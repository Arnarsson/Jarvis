"""Whisper-based transcription service using faster-whisper."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class TranscriptSegment:
    """A segment of transcribed text with timing."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """Complete transcription result."""

    language: str
    language_probability: float
    duration: float
    segments: list[TranscriptSegment]
    full_text: str


class TranscriptionService:
    """
    Transcription service using faster-whisper.

    Supports GPU acceleration with CUDA, falls back to CPU.
    """

    def __init__(
        self,
        model_size: str = "base",  # Start small, upgrade as needed
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        """
        Initialize transcription service.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: "cuda" for GPU, "cpu" for CPU, None for auto-detect
            compute_type: "float16" for GPU, "int8" for CPU, None for auto
        """
        from faster_whisper import WhisperModel

        # Auto-detect device if not specified
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        # Set compute type based on device
        if compute_type is None:
            compute_type = "float16" if device == "cuda" else "int8"

        self.device = device
        self.model_size = model_size
        self.compute_type = compute_type

        logger.info(
            "transcription_service_init",
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )

        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            language: Language code (e.g., "en"), None for auto-detect
            beam_size: Beam search size (higher = more accurate, slower)
            vad_filter: Use voice activity detection to skip silence

        Returns:
            TranscriptionResult with segments and full text
        """
        logger.info(
            "transcription_started",
            audio_path=str(audio_path),
            language=language,
        )

        segments_iter, info = self.model.transcribe(
            str(audio_path),
            language=language,
            beam_size=beam_size,
            vad_filter=vad_filter,
            vad_parameters={
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "min_silence_duration_ms": 500,
                "speech_pad_ms": 400,
            },
        )

        # Collect segments
        segments = []
        full_text_parts = []

        for segment in segments_iter:
            segments.append(
                TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                )
            )
            full_text_parts.append(segment.text.strip())

        full_text = " ".join(full_text_parts)

        result = TranscriptionResult(
            language=info.language,
            language_probability=info.language_probability,
            duration=info.duration,
            segments=segments,
            full_text=full_text,
        )

        logger.info(
            "transcription_completed",
            audio_path=str(audio_path),
            language=info.language,
            duration=info.duration,
            segment_count=len(segments),
            text_length=len(full_text),
        )

        return result


# Singleton instance for reuse
_service: Optional[TranscriptionService] = None


def get_transcription_service() -> TranscriptionService:
    """Get or create transcription service singleton."""
    global _service
    if _service is None:
        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        _service = TranscriptionService(model_size=model_size)
    return _service
