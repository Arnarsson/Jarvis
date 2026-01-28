"""Helper functions to build WhyPayload from different sources.

Provides utilities to construct transparent explanations for suggestions
with confidence scores and source links.
"""

from datetime import datetime, timezone
from typing import Any

import structlog

from jarvis_server.api.models import Source, WhyPayload

logger = structlog.get_logger(__name__)


def build_why_payload(
    reasons: list[str],
    confidence: float,
    sources: list[dict[str, Any]]
) -> WhyPayload:
    """Build a WhyPayload from raw data.
    
    Args:
        reasons: Plain English explanation strings
        confidence: Score from 0.0 to 1.0
        sources: List of source dicts with keys: type, id, timestamp, snippet, url (optional)
    
    Returns:
        WhyPayload instance
    
    Example:
        >>> why = build_why_payload(
        ...     reasons=["Sender is VIP", "Contains deadline"],
        ...     confidence=0.85,
        ...     sources=[{
        ...         "type": "email",
        ...         "id": "msg_123",
        ...         "timestamp": datetime.now(),
        ...         "snippet": "Can you send by Friday?",
        ...         "url": "/email/msg_123"
        ...     }]
        ... )
    """
    try:
        source_objects = [Source(**s) for s in sources]
        return WhyPayload(
            reasons=reasons,
            confidence=confidence,
            sources=source_objects
        )
    except Exception as e:
        logger.error("why_payload_build_failed", error=str(e), reasons=reasons)
        raise


def build_why_from_email(
    email_id: str,
    email_snippet: str,
    email_timestamp: datetime,
    reasons: list[str],
    confidence: float,
    additional_sources: list[dict[str, Any]] | None = None
) -> WhyPayload:
    """Build WhyPayload with an email as the primary source.
    
    Args:
        email_id: Email message ID
        email_snippet: First ~200 chars of email body
        email_timestamp: When the email was received
        reasons: Why this email is important
        confidence: Confidence score 0-1
        additional_sources: Optional additional sources
    
    Returns:
        WhyPayload with email as primary source
    """
    sources = [{
        "type": "email",
        "id": email_id,
        "timestamp": email_timestamp,
        "snippet": email_snippet[:200],
        "url": f"/email/{email_id}"
    }]
    
    if additional_sources:
        sources.extend(additional_sources)
    
    return build_why_payload(reasons, confidence, sources)


def build_why_from_capture(
    capture_id: str,
    capture_text: str,
    capture_timestamp: datetime,
    reasons: list[str],
    confidence: float,
    additional_sources: list[dict[str, Any]] | None = None
) -> WhyPayload:
    """Build WhyPayload with a screen capture as the primary source.
    
    Args:
        capture_id: Capture UUID
        capture_text: OCR text from capture
        capture_timestamp: When the capture was taken
        reasons: Why this capture is relevant
        confidence: Confidence score 0-1
        additional_sources: Optional additional sources
    
    Returns:
        WhyPayload with capture as primary source
    """
    sources = [{
        "type": "capture",
        "id": capture_id,
        "timestamp": capture_timestamp,
        "snippet": capture_text[:200] if capture_text else "[No text extracted]",
        "url": f"/timeline?capture={capture_id}"
    }]
    
    if additional_sources:
        sources.extend(additional_sources)
    
    return build_why_payload(reasons, confidence, sources)


def build_why_from_calendar(
    event_id: str,
    event_title: str,
    event_start: datetime,
    reasons: list[str],
    confidence: float,
    additional_sources: list[dict[str, Any]] | None = None
) -> WhyPayload:
    """Build WhyPayload with a calendar event as the primary source.
    
    Args:
        event_id: Calendar event ID
        event_title: Event title/summary
        event_start: Event start time
        reasons: Why this event matters
        confidence: Confidence score 0-1
        additional_sources: Optional additional sources
    
    Returns:
        WhyPayload with calendar event as primary source
    """
    sources = [{
        "type": "calendar",
        "id": event_id,
        "timestamp": event_start,
        "snippet": event_title[:200],
        "url": f"/calendar?event={event_id}"
    }]
    
    if additional_sources:
        sources.extend(additional_sources)
    
    return build_why_payload(reasons, confidence, sources)


def build_why_from_conversation(
    conversation_id: str,
    conversation_title: str,
    conversation_date: datetime,
    reasons: list[str],
    confidence: float,
    additional_sources: list[dict[str, Any]] | None = None
) -> WhyPayload:
    """Build WhyPayload with an AI conversation as the primary source.
    
    Args:
        conversation_id: Conversation UUID
        conversation_title: Conversation title
        conversation_date: When the conversation occurred
        reasons: Why this conversation is relevant
        confidence: Confidence score 0-1
        additional_sources: Optional additional sources
    
    Returns:
        WhyPayload with conversation as primary source
    """
    sources = [{
        "type": "conversation",
        "id": conversation_id,
        "timestamp": conversation_date,
        "snippet": conversation_title[:200],
        "url": f"/search?conversation={conversation_id}"
    }]
    
    if additional_sources:
        sources.extend(additional_sources)
    
    return build_why_payload(reasons, confidence, sources)


def build_why_from_pattern(
    pattern_id: str,
    pattern_description: str,
    pattern_last_seen: datetime,
    reasons: list[str],
    confidence: float,
    source_conversation_ids: list[str] | None = None
) -> WhyPayload:
    """Build WhyPayload for a detected pattern.
    
    Args:
        pattern_id: Pattern UUID
        pattern_description: Pattern description
        pattern_last_seen: When pattern was last detected
        reasons: Why this pattern matters
        confidence: Confidence score 0-1
        source_conversation_ids: Optional list of conversation IDs that contributed
    
    Returns:
        WhyPayload for pattern with conversation sources if available
    """
    sources = [{
        "type": "conversation",
        "id": pattern_id,
        "timestamp": pattern_last_seen,
        "snippet": pattern_description[:200],
        "url": f"/workflows?pattern={pattern_id}"
    }]
    
    # Add source conversations if available
    if source_conversation_ids:
        for conv_id in source_conversation_ids[:5]:  # Limit to 5 sources
            sources.append({
                "type": "conversation",
                "id": conv_id,
                "timestamp": pattern_last_seen,
                "snippet": "Related conversation",
                "url": f"/search?conversation={conv_id}"
            })
    
    return build_why_payload(reasons, confidence, sources)


def merge_why_payloads(payloads: list[WhyPayload]) -> WhyPayload:
    """Merge multiple WhyPayloads into a single comprehensive explanation.
    
    Useful when a suggestion is informed by multiple independent sources.
    Takes the minimum confidence and combines all reasons and sources.
    
    Args:
        payloads: List of WhyPayload objects to merge
    
    Returns:
        Single merged WhyPayload
    """
    if not payloads:
        raise ValueError("Cannot merge empty list of payloads")
    
    if len(payloads) == 1:
        return payloads[0]
    
    all_reasons = []
    all_sources = []
    min_confidence = 1.0
    
    for payload in payloads:
        all_reasons.extend(payload.reasons)
        all_sources.extend(payload.sources)
        min_confidence = min(min_confidence, payload.confidence)
    
    # Deduplicate reasons (preserve order)
    unique_reasons = []
    seen = set()
    for reason in all_reasons:
        if reason not in seen:
            unique_reasons.append(reason)
            seen.add(reason)
    
    return WhyPayload(
        reasons=unique_reasons,
        confidence=min_confidence,
        sources=all_sources
    )
