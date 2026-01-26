"""Pattern detector for identifying repeated action sequences from screen captures."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import Capture, Pattern


@dataclass
class DetectedPattern:
    """A detected pattern candidate."""
    pattern_type: str
    name: str
    description: str
    trigger_conditions: dict
    actions: list
    confidence: float
    similar_captures: list[str]


class PatternDetector:
    """Detects repeated action patterns from screen captures.
    
    Pattern types:
    - REPETITIVE_ACTION: Same action done frequently (same app + similar text)
    - TIME_BASED: Action at specific times (e.g., daily at 9am)
    - TRIGGER_RESPONSE: Action following another action
    - WORKFLOW_SEQUENCE: Series of related actions
    """

    def __init__(self, session: AsyncSession, qdrant_client=None):
        self.session = session
        self.qdrant_client = qdrant_client
        
        # Configuration
        self.similarity_threshold = 0.85
        self.min_frequency_for_pattern = 3
        self.lookback_hours = 168  # 1 week

    async def detect_patterns(self, capture_id: str) -> list[DetectedPattern]:
        """Analyze a capture and detect potential patterns."""
        patterns = []
        
        # Get the capture
        result = await self.session.execute(
            select(Capture).where(Capture.id == capture_id)
        )
        capture = result.scalar_one_or_none()
        if not capture or not capture.ocr_text:
            return patterns
        
        # Check for similar captures (repetitive actions)
        similar = await self._find_similar_captures(capture)
        if len(similar) >= self.min_frequency_for_pattern:
            pattern = self._create_repetitive_pattern(capture, similar)
            if pattern:
                patterns.append(pattern)
        
        # Check for time-based patterns
        time_pattern = await self._check_time_based_pattern(capture)
        if time_pattern:
            patterns.append(time_pattern)
        
        return patterns

    async def _find_similar_captures(self, capture: Capture) -> list[Capture]:
        """Find captures with similar content."""
        if not self.qdrant_client:
            # Fallback to simple text matching
            return await self._find_similar_by_text(capture)
        
        # Use vector similarity from Qdrant
        # TODO: Implement when Qdrant search is integrated
        return await self._find_similar_by_text(capture)

    async def _find_similar_by_text(self, capture: Capture) -> list[Capture]:
        """Find similar captures by text content (fallback without vectors)."""
        if not capture.ocr_text:
            return []
        
        # Extract key terms from OCR text
        text = capture.ocr_text.lower()
        
        # Get captures from the last week
        lookback = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        result = await self.session.execute(
            select(Capture)
            .where(Capture.timestamp >= lookback)
            .where(Capture.id != capture.id)
            .where(Capture.ocr_text.isnot(None))
        )
        candidates = result.scalars().all()
        
        # Simple text similarity - find captures with overlapping content
        similar = []
        for candidate in candidates:
            if candidate.ocr_text:
                similarity = self._text_similarity(text, candidate.ocr_text.lower())
                if similarity >= self.similarity_threshold:
                    similar.append(candidate)
        
        return similar

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity using word overlap (Jaccard)."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def _create_repetitive_pattern(
        self,
        capture: Capture,
        similar_captures: list[Capture],
    ) -> Optional[DetectedPattern]:
        """Create a pattern from repetitive actions."""
        # Extract common elements
        texts = [capture.ocr_text or ""] + [c.ocr_text or "" for c in similar_captures]
        common_words = self._find_common_words(texts)
        
        if not common_words:
            return None
        
        # Generate pattern name
        name = f"Repetitive: {' '.join(list(common_words)[:5])}"
        
        return DetectedPattern(
            pattern_type="REPETITIVE_ACTION",
            name=name,
            description=f"Detected {len(similar_captures) + 1} similar screen captures with common content",
            trigger_conditions={
                "type": "text_match",
                "keywords": list(common_words)[:10],
            },
            actions=[
                {"type": "notify", "message": f"You're doing this again: {name}"}
            ],
            confidence=min(len(similar_captures) / 10, 0.9),
            similar_captures=[capture.id] + [c.id for c in similar_captures[:5]],
        )

    def _find_common_words(self, texts: list[str]) -> set[str]:
        """Find words that appear in all texts."""
        if not texts:
            return set()
        
        word_sets = [set(t.lower().split()) for t in texts if t]
        if not word_sets:
            return set()
        
        common = word_sets[0]
        for ws in word_sets[1:]:
            common = common & ws
        
        # Filter out short/common words
        common = {w for w in common if len(w) > 3}
        return common

    async def _check_time_based_pattern(self, capture: Capture) -> Optional[DetectedPattern]:
        """Check if this capture matches a time-based pattern."""
        # Get captures at similar times (same hour) from previous days
        capture_hour = capture.timestamp.hour
        
        lookback = datetime.now(timezone.utc) - timedelta(days=7)
        result = await self.session.execute(
            select(Capture)
            .where(Capture.timestamp >= lookback)
            .where(Capture.id != capture.id)
            .where(func.extract("hour", Capture.timestamp) == capture_hour)
            .where(Capture.ocr_text.isnot(None))
        )
        same_hour_captures = list(result.scalars().all())
        
        if len(same_hour_captures) >= self.min_frequency_for_pattern:
            # Check if content is also similar
            similar_at_time = [
                c for c in same_hour_captures
                if c.ocr_text and self._text_similarity(
                    capture.ocr_text or "",
                    c.ocr_text
                ) >= 0.5
            ]
            
            if len(similar_at_time) >= self.min_frequency_for_pattern:
                return DetectedPattern(
                    pattern_type="TIME_BASED",
                    name=f"Daily at {capture_hour}:00",
                    description=f"Similar activity detected at {capture_hour}:00 on {len(similar_at_time)} days",
                    trigger_conditions={
                        "type": "time",
                        "hour": capture_hour,
                        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    },
                    actions=[
                        {"type": "notify", "message": f"Time for your {capture_hour}:00 routine"}
                    ],
                    confidence=min(len(similar_at_time) / 7, 0.8),
                    similar_captures=[capture.id] + [c.id for c in similar_at_time[:5]],
                )
        
        return None

    async def analyze_recent(self, hours: int = 24) -> list[dict]:
        """Analyze recent captures for pattern candidates."""
        lookback = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(Capture)
            .where(Capture.timestamp >= lookback)
            .where(Capture.ocr_text.isnot(None))
            .order_by(Capture.timestamp.desc())
        )
        captures = list(result.scalars().all())
        
        candidates = []
        analyzed_ids = set()
        
        for capture in captures:
            if capture.id in analyzed_ids:
                continue
            
            patterns = await self.detect_patterns(capture.id)
            for pattern in patterns:
                analyzed_ids.update(pattern.similar_captures)
                candidates.append({
                    "pattern": pattern,
                    "source_capture_id": capture.id,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
        
        return candidates
